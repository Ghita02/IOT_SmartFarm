import json
import sqlite3
import uuid

from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "smartfarm.db"


class DTFactory:
    """
    SQLite adaptation of the course framework DTFactory.

    Preserves the main factory operations while using SQLite
    instead of the original MongoDB-specific database API.
    """

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DATABASE_PATH
        self._init_dt_collection()

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection

    def _init_dt_collection(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS digital_twins (
                    _id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    digital_replicas TEXT DEFAULT '[]',
                    services TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT DEFAULT 'active'
                )
            """)

    def create_dt(self, name, description=""):
        dt_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO digital_twins
                (_id, name, description, digital_replicas,
                 services, created_at, updated_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dt_id, name, description, "[]", "[]",
                now, now, "active"
            ))

        return dt_id

    def add_digital_replica(self, dt_id, dr_type, dr_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT digital_replicas FROM digital_twins WHERE _id = ?",
                (dt_id,)
            ).fetchone()

            if row is None:
                raise ValueError(f"Digital Twin not found: {dt_id}")

            replicas = json.loads(row["digital_replicas"])
            replicas.append({"type": dr_type, "id": dr_id})

            conn.execute("""
                UPDATE digital_twins
                SET digital_replicas = ?, updated_at = ?
                WHERE _id = ?
            """, (
                json.dumps(replicas),
                datetime.now().isoformat(),
                dt_id
            ))

    def add_service(self, dt_id, service_name, service_config=None):
        service_data = {
            "name": service_name,
            "config": service_config or {},
            "status": "active",
            "added_at": datetime.now().isoformat(),
        }

        with self._connect() as conn:
            row = conn.execute(
                "SELECT services FROM digital_twins WHERE _id = ?",
                (dt_id,)
            ).fetchone()

            if row is None:
                raise ValueError(f"Digital Twin not found: {dt_id}")

            services = json.loads(row["services"])
            services.append(service_data)

            conn.execute("""
                UPDATE digital_twins
                SET services = ?, updated_at = ?
                WHERE _id = ?
            """, (
                json.dumps(services),
                datetime.now().isoformat(),
                dt_id
            ))

    def get_dt(self, dt_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM digital_twins WHERE _id = ?",
                (dt_id,)
            ).fetchone()

        if row is None:
            return None

        result = dict(row)
        result["digital_replicas"] = json.loads(result["digital_replicas"])
        result["services"] = json.loads(result["services"])
        return result

    def list_dts(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM digital_twins ORDER BY created_at DESC"
            ).fetchall()

        results = []
        for row in rows:
            item = dict(row)
            item["digital_replicas"] = json.loads(item["digital_replicas"])
            item["services"] = json.loads(item["services"])
            results.append(item)

        return results

    def create_dt_from_data(self, dt_data):
        # Reconstruct the SmartFarm twin and its framework replicas.
        from src.digital_twin.core import SmartFarmDigitalTwin

        smartfarm_twin = SmartFarmDigitalTwin()
        framework_twin = smartfarm_twin.framework_twin

        for replica_ref in dt_data.get("digital_replicas", []):
            replica = replica_ref.get("data")

            if replica:
                framework_twin.add_digital_replica(replica)

        return framework_twin

    def get_dt_instance(self, dt_id):
        dt_data = self.get_dt(dt_id)

        if not dt_data:
            return None

        return self.create_dt_from_data(dt_data)
