import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "synthetic")
TIMEOUT = 60


def headers(prefer="return=minimal"):
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def load_json(filename):
    with open(os.path.join(DATA_DIR, f"{filename}.json")) as f:
        return json.load(f)


def upsert(table: str, data: list[dict]):
    for i in range(0, len(data), 100):
        chunk = data[i : i + 100]
        resp = httpx.post(
            f"{SB_URL}/rest/v1/{table}",
            headers={**headers("return=representation,resolution=merge-duplicates")},
            json=chunk,
            timeout=TIMEOUT,
        )
        if resp.status_code >= 400:
            print(f"  ✗ {table} chunk {i}: {resp.status_code} {resp.text[:200]}")
            return False
    return True


def seed_corridors():
    data = load_json("corridors")
    rows = [{"corridor_id": c["corridor_id"], "name": c["name"],
             "section": c["section"], "capacity": c.get("capacity", 2)}
            for c in data]
    ok = upsert("corridors", rows)
    print(f"  {'✓' if ok else '✗'} Corridors: {len(rows)}")
    return ok


def seed_assets():
    data = load_json("assets")
    rows = [{"asset_id": a["asset_id"], "department": a["department"],
             "asset_type": a["asset_type"], "corridor_id": a["corridor_id"],
             "location": a["location"], "criticality": a["criticality"],
             "current_status": a["current_status"],
             "availability": a["availability"],
             "historical_failure_rate": a["historical_failure_rate"]}
            for a in data]
    ok = upsert("assets", rows)
    print(f"  {'✓' if ok else '✗'} Assets: {len(rows)}")
    return ok


def seed_tasks():
    data = load_json("tasks")
    rows = [{
        "task_id": t["task_id"], "asset_id": t["asset_id"],
        "department": t["department"], "task_type": t["task_type"],
        "priority_score": t["priority_score"],
        "criticality": t["criticality"], "failure_risk": t["failure_risk"],
        "days_overdue": t["days_overdue"],
        "safety_criticality": t["safety_criticality"],
        "train_impact": t["train_impact"],
        "due_date": t["due_date"],
        "estimated_duration_minutes": t["estimated_duration_minutes"],
        "required_block_type": t["required_block_type"],
        "required_resources": t.get("required_resources", []),
        "safety_requirements": t.get("safety_requirements", []),
        "isolation_required": t.get("isolation_required", False),
        "dependencies": t.get("dependencies", []),
        "corridor_id": t["corridor_id"], "location": t["location"],
        "status": t.get("status", "Pending"),
        "assigned_block_id": t.get("assigned_block_id"),
        "explanation": t.get("explanation", ""),
    } for t in data]
    ok = upsert("maintenance_tasks", rows)
    print(f"  {'✓' if ok else '✗'} Tasks: {len(rows)}")
    return ok


def seed_trains():
    data = load_json("trains")
    rows = [{"train_id": t["train_id"], "train_type": t["train_type"],
             "route": t["route"], "corridor_id": t["corridor_id"],
             "scheduled_time": t["scheduled_time"],
             "priority": t["priority"], "direction": t["direction"]}
            for t in data]
    ok = upsert("trains", rows)
    print(f"  {'✓' if ok else '✗'} Trains: {len(rows)}")
    return ok


def seed_block_windows():
    data = load_json("block_windows")
    rows = [{"window_id": w["window_id"], "corridor_id": w["corridor_id"],
             "start_time": w["start_time"], "end_time": w["end_time"],
             "block_type": w["block_type"], "day_of_week": w["day_of_week"]}
            for w in data]
    ok = upsert("block_windows", rows)
    print(f"  {'✓' if ok else '✗'} Block Windows: {len(rows)}")
    return ok


def main():
    if not SB_URL or not SB_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        sys.exit(1)

    print(f"Seeding Supabase: {SB_URL}")
    print()

    all_ok = True
    all_ok &= seed_corridors()
    all_ok &= seed_assets()
    all_ok &= seed_tasks()
    all_ok &= seed_trains()
    all_ok &= seed_block_windows()

    print()
    if all_ok:
        print("✅ All data seeded successfully!")
    else:
        print("⚠️  Some tables had errors — check output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
