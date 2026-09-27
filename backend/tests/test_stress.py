
"""Stress & robustness tests — the failure paths a load test would hit.

These are deliberately DB-free: they exercise middleware, request
validation and the inspection upload path only, so they run on a fresh
clone without Supabase configured. True concurrency (parallel optimizer
runs, mixed read/write load) is covered by scripts/stress_load.py against
a running server.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.core.middleware import rate_limiter, login_rate_limiter

client = TestClient(app)


def _auth_headers():
    # One token carrying every role so each endpoint's guard passes.
    token = create_access_token({
        "sub": "stress_tester",
        "roles": ["admin", "planner", "operations", "engineer"],
    })
    return {"Authorization": f"Bearer {token}"}


def _hostile_json(payload: dict) -> bytes:
    """Serialize a payload containing non-finite floats the way a naive
    client would: json.dumps(allow_nan=True) emits bare NaN/Infinity
    literals. Sent as raw bytes because httpx>=0.28's json= parameter
    refuses to serialize them CLIENT-SIDE — which would abort the request
    before it ever reaches the server and test the HTTP library, not us."""
    return json.dumps(payload, allow_nan=True).encode()


def _post_json(path: str, payload: dict):
    return client.post(
        path,
        content=_hostile_json(payload),
        headers={**_auth_headers(), "Content-Type": "application/json"},
    )


def _put_json(path: str, payload: dict):
    return client.put(
        path,
        content=_hostile_json(payload),
        headers={**_auth_headers(), "Content-Type": "application/json"},
    )


@pytest.fixture(autouse=True)
def _isolate_rate_limiters():
    """Snapshot limiter state around every test so the intentional bursts
    below cannot leak into other tests (both files share the app)."""
    def snap(limiter):
        return (
            {k: list(v) for k, v in limiter.minute_windows.items()},
            {k: list(v) for k, v in limiter.hour_windows.items()},
        )

    limiters = (rate_limiter, login_rate_limiter)
    before = [snap(l) for l in limiters]
    # Start each test with an empty bucket: traffic accumulated by other
    # test files (same shared 'testclient' identity) could otherwise leave
    # the budget already exhausted and turn a plain request into a 429.
    for limiter in limiters:
        limiter.minute_windows.clear()
        limiter.hour_windows.clear()
    yield
    for limiter, (minutes, hours) in zip(limiters, before):
        limiter.minute_windows.clear()
        limiter.minute_windows.update(minutes)
        limiter.hour_windows.clear()
        limiter.hour_windows.update(hours)


class TestRateLimitingUnderLoad:

    def test_burst_beyond_limit_gets_429_json_not_500(self):
        """The limiter used to raise HTTPException from the outermost
        middleware, which escaped the app's handlers as an opaque 500."""
        limit = rate_limiter.requests_per_minute
        if rate_limiter.requests_per_hour < limit + 5:
            pytest.skip("hourly rate limit too low for this test")

        resp = None
        # Unauthenticated requests — the limiter runs before auth, so no DB
        # traffic either way.
        for _ in range(limit + 3):
            resp = client.get("/api/data/assets")
            if resp.status_code == 429:
                break

        assert resp is not None and resp.status_code == 429, (
            f"expected 429 after {limit} requests, got {resp.status_code if resp else 'no response'}"
        )
        body = resp.json()
        assert "detail" in body, "429 body must be JSON with FastAPI's detail field"
        assert "Retry-After" in resp.headers
        # Security headers must still be applied to limiter responses
        # (middleware ordering: SecurityHeaders wraps RateLimit).
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_login_burst_hits_dedicated_limiter_not_global(self):
        """Credential endpoints used to be fully exempt: unlimited password
        guessing. They now have their own tighter budget."""
        limit = login_rate_limiter.requests_per_minute
        last = None
        for _ in range(limit + 2):
            last = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "definitely-wrong"},
            )
            if last.status_code == 429:
                break

        assert last is not None and last.status_code == 429
        assert "detail" in last.json()

        # ...and the global limiter was not consumed by the login traffic.
        resp = client.get("/api/data/assets")
        assert resp.status_code == 401, (
            "login traffic must not eat into the global rate-limit budget"
        )


class TestMalformedBodies:

    def test_revert_rejects_malformed_json_with_400(self):
        """Manual body parsing used to let JSONDecodeError escape as a 500."""
        resp = client.post(
            "/api/plans/revert",
            content=b"{not valid json",
            headers={**_auth_headers(), "Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "detail" in resp.json()

    def test_approve_rejects_malformed_json_with_400(self):
        resp = client.post(
            "/api/plans/approve",
            content=b"also not json",
            headers={**_auth_headers(), "Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_revert_requires_plan_id(self):
        resp = client.post("/api/plans/revert", json={}, headers=_auth_headers())
        assert resp.status_code == 400

    def test_revert_rejects_non_list_block_ids(self):
        resp = client.post(
            "/api/plans/revert",
            json={"plan_id": "PLAN-x", "block_ids": "not-a-list"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400

    def test_commit_rejects_unknown_decision(self):
        resp = client.post(
            "/api/inspection/workflow/WF-nonexistent/commit",
            json={"decision": 123},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400

    def test_commit_unknown_workflow_is_404(self):
        resp = client.post(
            "/api/inspection/workflow/WF-nonexistent/commit",
            json={"decision": "approve"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 404


class TestScenarioValidation:
    """A single hostile /simulate payload used to hang the process:
    traffic_forecast_change=1e9 appended ~75 billion Train objects."""

    @pytest.mark.parametrize("bad", [1e9, float("inf"), float("nan"), 12345.0])
    def test_simulate_rejects_unbounded_traffic_change(self, bad):
        resp = _post_json("/api/simulate", {"traffic_forecast_change": bad})
        assert resp.status_code == 422

    @pytest.mark.parametrize("bad", [101.0, -101.0, float("inf")])
    def test_simulate_rejects_out_of_range_resource_change(self, bad):
        resp = _post_json("/api/simulate", {"resource_availability_change": bad})
        assert resp.status_code == 422

    @pytest.mark.parametrize("bad", [1, 999, 14, 481])
    def test_simulate_rejects_out_of_range_block_duration(self, bad):
        resp = client.post(
            "/api/simulate",
            json={"block_duration_override": bad},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_simulate_rejects_poisoned_criticality_values(self):
        resp = _post_json(
            "/api/simulate",
            {"asset_criticality_changes": {"ENG-AST-0001": float("nan")}},
        )
        assert resp.status_code == 422

        resp = _post_json(
            "/api/simulate",
            {"asset_criticality_changes": {"ENG-AST-0001": 150.0}},
        )
        assert resp.status_code == 422


class TestWeightValidation:
    """NaN/inf/negative weights used to flow straight into the priority
    engine (NaN also crashed the optimizer's int(round(nan))). Validation
    happens before the handler runs, so no database is touched."""

    @pytest.mark.parametrize(
        "bad", [float("nan"), float("inf"), float("-inf"), -0.5, 1.5]
    )
    def test_weights_reject_bad_values(self, bad):
        resp = _put_json("/api/priority/weights", {"asset_criticality": bad})
        assert resp.status_code == 422


class TestUploadLimits:

    def test_garbage_image_returns_400(self):
        resp = client.post(
            "/api/inspection/analyze",
            files={"file": ("garbage.jpg", b"this is not an image", "image/jpeg")},
            data={"asset_type": "track"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400

    def test_oversized_upload_returns_413(self):
        """Uploads used to be read whole into memory — an OOM vector."""
        payload = b"\xff\xd8" + b"\x00" * (16 * 1024 * 1024)  # 16 MB fake JPEG
        resp = client.post(
            "/api/inspection/analyze",
            files={"file": ("huge.jpg", payload, "image/jpeg")},
            data={"asset_type": "track"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 413

    def test_invalid_asset_type_returns_422(self):
        resp = client.post(
            "/api/inspection/analyze",
            files={"file": ("x.jpg", b"\xff\xd8", "image/jpeg")},
            data={"asset_type": "submarine"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


class TestSamplePredictions:

    def test_sample_error_path_returns_entry_not_nameerror(self, monkeypatch):
        """The /samples handler referenced an undefined `asset_type` in its
        except branch, so ANY inference failure became a NameError 500
        instead of a graceful per-sample error entry."""
        from app.api import inspection

        def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated inference failure")

        monkeypatch.setattr(inspection.cv, "run_inference_auto", _boom)

        resp = client.get("/api/inspection/samples", headers=_auth_headers())
        assert resp.status_code == 200
        samples = resp.json()["samples"]
        if not samples:
            pytest.skip("no bundled sample images found")
        for sample in samples:
            assert sample.get("asset_type") == "auto"
            assert "error" in sample


class TestWorkflowStoreBounds:

    def test_workflow_store_is_bounded(self):
        """_WORKFLOWS grew without limit — a memory leak under sustained
        workflow traffic."""
        from app.api import inspection

        saved = dict(inspection._WORKFLOWS)
        try:
            inspection._WORKFLOWS.clear()
            for i in range(inspection._MAX_WORKFLOWS + 5):
                inspection._store_workflow({"workflow_id": f"WF-{i:04d}", "n": i})
            assert len(inspection._WORKFLOWS) == inspection._MAX_WORKFLOWS
            # Oldest entries evicted first (FIFO).
            assert "WF-0000" not in inspection._WORKFLOWS
            assert "WF-0004" not in inspection._WORKFLOWS
            assert f"WF-{inspection._MAX_WORKFLOWS + 4:04d}" in inspection._WORKFLOWS
        finally:
            inspection._WORKFLOWS.clear()
            inspection._WORKFLOWS.update(saved)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
