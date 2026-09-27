import json
import random
import os
from datetime import datetime, date, timedelta

random.seed(42)

CORRIDORS = [
    {"corridor_id": "C-07", "name": "Delhi-Mumbai Main Line", "section": "Delhi-Palwal", "capacity": 2},
    {"corridor_id": "C-12", "name": "Howrah-Delhi Line", "section": "Mughal Sarai-Allahabad", "capacity": 2},
    {"corridor_id": "C-19", "name": "Chennai-Mumbai Line", "section": "Nagpur-Bhusawal", "capacity": 2},
]

ASSET_TYPES = {
    "Engineering": [
        "Track Section", "Rail Joint", "Sleeper", "Ballast Bed",
        "Turnout", "Level Crossing", "Bridge", "Culvert", "Fencing"
    ],
    "S&T": [
        "Signal", "Point Machine", "Track Circuit", "Level Crossing Gate",
        "Interlocking", "Telecom Tower", "Cable Route", "Relay", "Block Instrument"
    ],
    "Traction": [
        "OHE Mast", "Contact Wire", "Catenary", "Traction Transformer",
        "Feeder", "Section Insulator", "Anchor", "Dropper", "Return Conductor"
    ]
}

SAFETY_REQUIREMENTS = [
    "Power Block Required", "Track Isolation", "Signal Override",
    "Speed Restriction", "Lookout Man Required", "Continuous Welded Rail Protocol",
    "Emergency Access Required"
]

RESOURCES = {
    "Engineering": ["Track Gang", "Welding Team", "Ballast Team", "Bridge Inspection Team", "Survey Team"],
    "S&T": ["Signal Technician", "Telecom Team", "Interlocking Team", "Cable Jointing Team"],
    "Traction": ["OHE Team", "Electrical Engineer", "Traction Maintenance Crew", "Isolation Team"]
}

TRAIN_TYPES = [
    ("Rajdhani", "Passenger"), ("Shatabdi", "Passenger"), ("Duronto", "Passenger"),
    ("Mail", "Passenger"), ("Express", "Passenger"), ("Passenger", "Passenger"),
    ("AC Express", "Passenger"), ("Superfast", "Passenger"),
    ("Freight", "Goods"), ("Container", "Goods"), ("Coal Rake", "Goods"),
    ("Oil Tanker", "Goods"), ("Parcel", "Goods"),
]


def generate_assets():
    assets = []
    asset_counter = 1

    for dept, types in ASSET_TYPES.items():
        dept_prefix = {"Engineering": "ENG", "S&T": "SMMS", "Traction": "TDMS"}[dept]
        for i in range(50):
            asset_type = types[i % len(types)]
            corridor = CORRIDORS[i % len(CORRIDORS)]
            assets.append({
                "asset_id": f"{dept_prefix}-AST-{asset_counter:04d}",
                "department": dept,
                "asset_type": asset_type,
                "corridor_id": corridor["corridor_id"],
                "location": f"KM {random.randint(10, 200)}.{random.randint(0, 9)}",
                "criticality": round(random.uniform(20, 100), 1),
                "current_status": random.choice(["Operational", "Operational", "Operational", "Degraded", "Under Maintenance"]),
                "availability": round(random.uniform(70, 100), 1),
                "historical_failure_rate": round(random.uniform(0.01, 0.15), 3),
            })
            asset_counter += 1

    return assets


def generate_tasks(assets):
    tasks = []
    task_counter = 1
    today = date.today()

    task_descriptions = {
        "Engineering": [
            ("Defect", "Rail fracture detected", 45),
            ("Defect", "Sleeper damage", 30),
            ("Overdue", "Ballast tamping overdue", 120),
            ("Preventive", "Annual track inspection", 180),
            ("Inspection", "Bridge structural inspection", 240),
            ("Defect", "Turnout malfunction", 60),
            ("Overdue", "Level crossing repair", 90),
            ("Emergency", "Emergency rail replacement", 180),
        ],
        "S&T": [
            ("Defect", "Signal lamp failure", 30),
            ("Defect", "Track circuit fault", 45),
            ("Overdue", "Interlocking maintenance overdue", 120),
            ("Preventive", "Telecom tower inspection", 90),
            ("Inspection", "Point machine inspection", 60),
            ("Defect", "Block instrument malfunction", 45),
            ("Overdue", "Cable route inspection overdue", 75),
            ("Emergency", "Signal system failure", 120),
        ],
        "Traction": [
            ("Defect", "OHE wire damage", 60),
            ("Defect", "Contact wire wear", 45),
            ("Overdue", "Transformer maintenance overdue", 180),
            ("Preventive", "Annual OHE inspection", 150),
            ("Inspection", "Feeder cable inspection", 90),
            ("Defect", "Section insulator failure", 60),
            ("Overdue", "Dropper replacement overdue", 45),
            ("Emergency", "Traction power failure", 120),
        ]
    }

    for dept in ["Engineering", "S&T", "Traction"]:
        dept_assets = [a for a in assets if a["department"] == dept]
        dept_prefix = {"Engineering": "ENG", "S&T": "SMMS", "Traction": "TDMS"}[dept]

        for i in range(100):
            asset = random.choice(dept_assets)
            desc = random.choice(task_descriptions[dept])
            task_type = desc[0]

            days_offset = random.randint(-14, 30)
            due = today + timedelta(days=days_offset)
            days_overdue = max(0, (today - due).days)

            base_criticality = asset["criticality"]
            if task_type == "Emergency":
                criticality = min(100, base_criticality + 30)
            elif task_type == "Defect":
                criticality = min(100, base_criticality + random.uniform(5, 20))
            else:
                criticality = base_criticality

            failure_risk = round(random.uniform(20, 95), 1)
            safety_crit = round(random.uniform(20, 90), 1)
            train_impact = round(random.uniform(10, 85), 1)

            duration = desc[2] + random.randint(-15, 30)
            duration = max(15, duration)

            tasks.append({
                "task_id": f"{dept_prefix}-{task_counter:03d}",
                "asset_id": asset["asset_id"],
                "department": dept,
                "task_type": task_type,
                "priority_score": 0.0,
                "criticality": round(criticality, 1),
                "failure_risk": failure_risk,
                "days_overdue": days_overdue,
                "safety_criticality": safety_crit,
                "train_impact": train_impact,
                "due_date": due.isoformat(),
                "estimated_duration_minutes": duration,
                "required_block_type": random.choice(["Possession", "Block", "Lines Up"]),
                "required_resources": random.sample(RESOURCES[dept], k=min(2, len(RESOURCES[dept]))),
                "safety_requirements": random.sample(SAFETY_REQUIREMENTS, k=random.randint(1, 3)),
                "isolation_required": random.random() > 0.6,
                "dependencies": [],
                "corridor_id": asset["corridor_id"],
                "location": asset["location"],
                "status": "Pending",
                "assigned_block_id": None,
                "explanation": ""
            })
            task_counter += 1

    return tasks


def generate_trains():
    trains = []
    hours = list(range(0, 24))

    for corridor in CORRIDORS:
        for i in range(25):
            train_type, category = random.choice(TRAIN_TYPES)
            hour = random.choice(hours)
            minute = random.choice([0, 15, 30, 45])
            trains.append({
                "train_id": f"{train_type[:3].upper()}-{random.randint(1000, 9999)}",
                "train_type": category,
                "route": f"{corridor['section']}",
                "corridor_id": corridor["corridor_id"],
                "scheduled_time": f"{hour:02d}:{minute:02d}",
                "priority": random.randint(1, 5),
                "direction": random.choice(["Up", "Down"])
            })

    return trains


def generate_block_windows():
    """Generate maintenance block windows.

    Durations (3h Block / 2h Possession / 2h Lines Up) are sized to fit
    the bulk of generated task durations (median ~110 min); nightly
    windows are the longest since they carry the least train traffic.
    """
    windows = []
    window_counter = 1

    for corridor in CORRIDORS:
        # 3 nightly Block windows (00:00-03:00) — longest safe durations
        for i in range(3):
            start_hour = 0 + i  # 00, 01, 02
            windows.append({
                "window_id": f"BW-{window_counter:03d}",
                "corridor_id": corridor["corridor_id"],
                "start_time": f"{start_hour:02d}:00",
                "end_time": f"{start_hour + 3:02d}:00",
                "block_type": "Block",
                "day_of_week": i
            })
            window_counter += 1

        # 2 Possession windows (2h) midday/afternoon
        for i in range(2):
            start_hour = random.choice([10, 11, 14, 15])
            windows.append({
                "window_id": f"BW-{window_counter:03d}",
                "corridor_id": corridor["corridor_id"],
                "start_time": f"{start_hour:02d}:00",
                "end_time": f"{start_hour + 2:02d}:00",
                "block_type": "Possession",
                "day_of_week": i
            })
            window_counter += 1

        # 2 Lines Up windows (2h)
        for i in range(2):
            start_hour = random.choice([6, 20])
            windows.append({
                "window_id": f"BW-{window_counter:03d}",
                "corridor_id": corridor["corridor_id"],
                "start_time": f"{start_hour:02d}:00",
                "end_time": f"{start_hour + 2:02d}:00",
                "block_type": "Lines Up",
                "day_of_week": i
            })
            window_counter += 1

    return windows


def generate_all_data():
    assets = generate_assets()
    tasks = generate_tasks(assets)
    trains = generate_trains()
    block_windows = generate_block_windows()

    return {
        "assets": assets,
        "tasks": tasks,
        "trains": trains,
        "corridors": CORRIDORS,
        "block_windows": block_windows
    }


def save_data(data_dir: str = "data/synthetic"):
    os.makedirs(data_dir, exist_ok=True)
    data = generate_all_data()

    for filename, content in data.items():
        filepath = os.path.join(data_dir, f"{filename}.json")
        with open(filepath, "w") as f:
            json.dump(content, f, indent=2, default=str)
        print(f"Generated {filepath}: {len(content)} records")

    return data


if __name__ == "__main__":
    save_data()
