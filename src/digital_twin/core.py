from datetime import datetime
from src.virtualization.digital_replica import DigitalReplicaManager


class SmartFarmDigitalTwin:
    """Coordinates the Digital Replicas representing the Smart Farm."""

    def __init__(self):
        self.twin_id = "smartfarm_001"
        self.name = "Smart Farm Digital Twin"
        self.created_at = datetime.now().isoformat(timespec="seconds")
        self.replicas = DigitalReplicaManager()

    def process_measurement(self, topic, value):
        return self.replicas.update_measurement(topic, value)

    def process_relay_status(self, state):
        self.replicas.update_relay(state)

    def get_state(self):
        return {
            "twin_id": self.twin_id,
            "name": self.name,
            "created_at": self.created_at,
            "replicas": self.replicas.get_all()
        }


digital_twin = SmartFarmDigitalTwin()