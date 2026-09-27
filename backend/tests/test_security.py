import os

import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import (
    create_access_token, decode_token, get_password_hash, verify_password,
    TokenData, UserRole
)
from app.core.validation import (
    validate_time_string, WhatIfScenarioValidator, WeightsUpdateValidator,
    PlanApprovalValidator, Sanitizer
)
from app.core.datastore import data_store
from app.core.audit import AuditEventType, log_audit
from app.models.domain import MaintenanceTask, PriorityWeights, Department, TaskStatus, BlockWindow, Train, TaskType
from app.ai.priority_engine import calculate_priority_score, calculate_all_priorities
from app.optimizer.block_optimizer import BlockOptimizer
from app.services.data_generator import generate_all_data


client = TestClient(app)

# DB-backed tests need Supabase credentials. Locally load_dotenv() has
# already pulled them from backend/.env by the time this module imports;
# in CI there is no .env, so these self-skip instead of failing. All
# middleware-, validation-, optimizer- and CV-related tests still run
# without a database.
requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL"),
    reason="requires Supabase credentials (SUPABASE_URL not set)",
)


class TestAuthentication:

    def test_password_hashing(self):
        password = "test123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed)
        assert not verify_password("wrong", hashed)

    def test_token_creation_and_validation(self):
        token = create_access_token({"sub": "testuser", "roles": ["planner"]})
        token_data = decode_token(token)
        assert token_data.username == "testuser"
        assert "planner" in token_data.roles

    def test_invalid_token(self):
        with pytest.raises(Exception):
            decode_token("invalid.token.here")

    def test_expired_token(self):
        import time
        from jose import jwt
        from app.core.security import SECRET_KEY, ALGORITHM
        payload = {"sub": "test", "roles": ["viewer"], "exp": int(time.time()) - 100, "type": "access"}
        expired_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(Exception):
            decode_token(expired_token)


class TestAuthorization:

    def test_admin_role_required(self):
        token = create_access_token({"sub": "viewer", "roles": ["viewer"]})
        response = client.get(
            "/api/audit/logs",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    @requires_db
    def test_planner_can_update_weights(self):
        token = create_access_token({"sub": "planner", "roles": ["planner"]})
        response = client.put(
            "/api/priority/weights",
            json={"asset_criticality": 0.4},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_viewer_cannot_update_weights(self):
        token = create_access_token({"sub": "viewer", "roles": ["viewer"]})
        response = client.put(
            "/api/priority/weights",
            json={"asset_criticality": 0.4},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    def test_operations_can_approve_plan(self):
        token = create_access_token({"sub": "operations", "roles": ["operations"]})
        response = client.post(
            "/api/plans/test-plan/approve",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in [200, 404]

    def test_unauthenticated_requests_rejected(self):
        response = client.get("/api/data/assets")
        assert response.status_code == 401


class TestInputValidation:

    def test_time_string_validation_valid(self):
        assert validate_time_string("00:00") == 0
        assert validate_time_string("12:30") == 750
        assert validate_time_string("23:59") == 1439

    def test_time_string_validation_invalid(self):
        with pytest.raises(ValueError):
            validate_time_string("24:00")
        with pytest.raises(ValueError):
            validate_time_string("12:60")
        with pytest.raises(ValueError):
            validate_time_string("abc")
        with pytest.raises(ValueError):
            validate_time_string("")

    def test_what_if_scenario_validation(self):
        scenario = WhatIfScenarioValidator(
            scenario_name="Test Scenario",
            block_duration_override=120,
            traffic_forecast_change=20.0,
            asset_criticality_changes={"ENG-AST-0001": 90.0},
            corridor_restrictions=["C-07"],
            resource_availability_change=-10.0
        )
        assert scenario.scenario_name == "Test Scenario"
        assert scenario.block_duration_override == 120

    def test_what_if_scenario_invalid_block_duration(self):
        with pytest.raises(ValueError):
            WhatIfScenarioValidator(block_duration_override=10)
        with pytest.raises(ValueError):
            WhatIfScenarioValidator(block_duration_override=500)

    def test_what_if_scenario_invalid_traffic_change(self):
        with pytest.raises(ValueError):
            WhatIfScenarioValidator(traffic_forecast_change=-150)
        with pytest.raises(ValueError):
            WhatIfScenarioValidator(traffic_forecast_change=600)

    def test_what_if_scenario_invalid_criticality(self):
        with pytest.raises(ValueError):
            WhatIfScenarioValidator(asset_criticality_changes={"INVALID@ID": 90.0})
        with pytest.raises(ValueError):
            WhatIfScenarioValidator(asset_criticality_changes={"ENG-AST-0001": 150.0})

    def test_weights_update_validation(self):
        weights = WeightsUpdateValidator(
            asset_criticality=0.3,
            failure_risk=0.25,
            overdue_factor=0.2,
            train_impact=0.15,
            safety_criticality=0.1
        )
        assert weights.asset_criticality == 0.3

    def test_weights_sum_validation(self):
        with pytest.raises(ValueError):
            WeightsUpdateValidator(
                asset_criticality=0.5,
                failure_risk=0.5,
                overdue_factor=0.5
            )

    def test_plan_approval_validation(self):
        approval = PlanApprovalValidator(action="approve")
        assert approval.action == "approve"

        approval = PlanApprovalValidator(action="reject", reason="Not feasible")
        assert approval.action == "reject"
        assert approval.reason == "Not feasible"

    def test_plan_approval_invalid_action(self):
        with pytest.raises(ValueError):
            PlanApprovalValidator(action="invalid")

    def test_sanitizer_string(self):
        assert Sanitizer.sanitize_string("  hello  ") == "hello"
        assert Sanitizer.sanitize_string("test\x00null") == "testnull"
        assert len(Sanitizer.sanitize_string("a" * 2000)) == 1000

    def test_sanitizer_list(self):
        result = Sanitizer.sanitize_list(["a", "b", "c"])
        assert result == ["a", "b", "c"]
        assert len(Sanitizer.sanitize_list(list(range(200)))) == 100

    def test_sanitizer_dict(self):
        result = Sanitizer.sanitize_dict({"key1": "value1", "key2": "value2"})
        assert result == {"key1": "value1", "key2": "value2"}


class TestRateLimiting:

    def test_rate_limit_headers_present(self):
        # Hit /api/auth/me rather than /api/data/assets: this test only
        # checks middleware headers, and /me needs no database — so it
        # still runs in CI where SUPABASE_URL is unset.
        token = create_access_token({"sub": "planner", "roles": ["planner"]})
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Remaining-Minute" in response.headers


class TestSecurityHeaders:

    def test_security_headers_present(self):
        # /api/auth/me: header assertions don't need the database (a 404
        # for an unknown user still carries every security header).
        token = create_access_token({"sub": "planner", "roles": ["planner"]})
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Content-Security-Policy" in response.headers


class TestAuditLogging:

    def test_audit_log_creation(self):
        log_audit(
            AuditEventType.USER_LOGIN,
            username="testuser",
            client_ip="127.0.0.1",
            status="success"
        )


class TestDataStore:

    def test_data_store_operations(self):
        data_store.set_assets([{"asset_id": "TEST-001", "criticality": 50}])
        assets = data_store.get_assets()
        assert len(assets) == 1
        assert assets[0]["asset_id"] == "TEST-001"

    def test_plan_versioning(self):
        plan = data_store.create_plan(
            {"blocks": [], "metrics": {}},
            "testuser"
        )
        assert "plan_id" in plan
        assert plan["version"] == 1
        assert plan["status"] == "Draft"

        approved = data_store.approve_plan(plan["plan_id"], "admin")
        assert approved is not None
        assert approved["status"] == "Approved"
        assert approved["version"] == 2

        history = data_store.get_plan_history(plan["plan_id"])
        assert len(history) == 2


class TestPriorityEngine:

    def test_priority_calculation(self):
        task = MaintenanceTask(
            task_id="TEST-001",
            asset_id="ENG-AST-0001",
            department=Department.ENGINEERING,
            task_type=TaskType.DEFECT,
            criticality=90.0,
            failure_risk=80.0,
            days_overdue=10,
            safety_criticality=70.0,
            train_impact=30.0,
            due_date=date.today()
        )
        weights = PriorityWeights()
        score = calculate_priority_score(task, weights)
        assert 0 <= score <= 100

    def test_priority_distribution(self):
        tasks = [
            MaintenanceTask(
                task_id=f"TEST-{i}",
                asset_id="ENG-AST-0001",
                department=Department.ENGINEERING,
                task_type=TaskType.DEFECT,
                criticality=90.0,
                failure_risk=80.0,
                days_overdue=10,
                safety_criticality=70.0,
                train_impact=30.0,
                due_date=date.today()
            )
            for i in range(10)
        ]
        weights = PriorityWeights()
        tasks = calculate_all_priorities(tasks, weights)
        assert len(tasks) == 10
        for i in range(len(tasks) - 1):
            assert tasks[i].priority_score >= tasks[i + 1].priority_score


class TestBlockOptimizer:

    def test_optimizer_basic(self):
        data = generate_all_data()
        tasks = [MaintenanceTask(**t) for t in data["tasks"]]
        windows = [BlockWindow(**w) for w in data["block_windows"]]
        trains = [Train(**t) for t in data["trains"]]

        weights = PriorityWeights()
        tasks = calculate_all_priorities(tasks, weights)

        optimizer = BlockOptimizer()
        blocks, metrics = optimizer.optimize(tasks, windows, trains)

        assert isinstance(blocks, list)
        assert metrics is not None
        assert metrics.total_tasks == len(tasks)


@requires_db
class TestAPIEndpoints:

    def get_admin_token(self):
        return create_access_token({"sub": "admin", "roles": ["admin", "planner", "operations"]})

    def get_planner_token(self):
        return create_access_token({"sub": "planner", "roles": ["planner"]})

    def test_health_endpoint(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_get_assets_authenticated(self):
        token = self.get_planner_token()
        response = client.get(
            "/api/data/assets",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_tasks_authenticated(self):
        token = self.get_planner_token()
        response = client.get(
            "/api/data/tasks",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_calculate_priorities(self):
        token = self.get_planner_token()
        response = client.get(
            "/api/priority/calculate",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert "distribution" in response.json()

    def test_update_weights(self):
        token = self.get_planner_token()
        response = client.put(
            "/api/priority/weights",
            json={"asset_criticality": 0.35},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_optimize(self):
        token = self.get_planner_token()
        response = client.post(
            "/api/optimize",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert "blocks" in response.json()

    def test_dashboard(self):
        token = self.get_planner_token()
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert "asset_availability" in response.json()

    def test_explain_task(self):
        token = self.get_planner_token()
        client.post("/api/optimize", headers={"Authorization": f"Bearer {token}"})
        tasks = client.get("/api/data/tasks", headers={"Authorization": f"Bearer {token}"}).json()
        if tasks:
            task_id = tasks[0]["task_id"]
            response = client.get(
                f"/api/explain/task/{task_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200

    def test_before_after_comparison(self):
        token = self.get_planner_token()
        response = client.get(
            "/api/comparison/before-after",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert "before" in response.json()
        assert "after" in response.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])