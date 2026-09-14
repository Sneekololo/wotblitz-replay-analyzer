import json
from pathlib import Path


def load_tank_db(path="tank_db.json", legacy_path="tank_db_old_version.json"):
    tank_db_path = Path(path)
    if not tank_db_path.exists():
        return {}

    with tank_db_path.open(encoding="utf-8") as tank_file:
        raw_tank_db = json.load(tank_file)

    if isinstance(raw_tank_db, list):
        tank_db = {
            int(tank["dev_id"]): dict(tank)
            for tank in raw_tank_db
            if tank.get("dev_id") is not None
        }
    else:
        tank_db = {int(key): dict(value) for key, value in raw_tank_db.items()}

    legacy_db_path = Path(legacy_path)
    if legacy_db_path.exists():
        with legacy_db_path.open(encoding="utf-8") as legacy_file:
            legacy_tank_db = json.load(legacy_file)
        if isinstance(legacy_tank_db, dict):
            for tank_id, tank in tank_db.items():
                legacy_tank = legacy_tank_db.get(str(tank_id))
                if legacy_tank and "type" not in tank and legacy_tank.get("type"):
                    tank["type"] = legacy_tank["type"]

    return tank_db
