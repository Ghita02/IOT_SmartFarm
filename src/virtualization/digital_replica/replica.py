from datetime import datetime


class DigitalReplica:
    """Digital representation of one physical Smart Farm component."""

    def __init__(self, replica_id, name, component_type, unit=None):
        self.replica_id = replica_id
        self.name = name
        self.component_type = component_type
        self.unit = unit
        self.value = None
        self.last_updated = None
        self.status = "unknown"

    def update(self, value):
        self.value = float(value)
        self.last_updated = datetime.now().isoformat(timespec="seconds")
        self.status = "online"

    def to_dict(self):
        return {
            "id": self.replica_id,
            "name": self.name,
            "type": self.component_type,
            "value": self.value,
            "unit": self.unit,
            "last_updated": self.last_updated,
            "status": self.status
        }


class DigitalReplicaManager:
    """Creates, stores, and updates the system's Digital Replicas."""

    def __init__(self):
        self.replicas = {
            "farm/temperature": DigitalReplica(
                "sensor_temperature", "Temperature Sensor", "sensor", "°C"
            ),
            "farm/humidity": DigitalReplica(
                "sensor_humidity", "Humidity Sensor", "sensor", "%"
            ),
            "farm/moisture": DigitalReplica(
                "sensor_moisture", "Soil Moisture Sensor", "sensor", "%"
            ),
            "farm/light": DigitalReplica(
                "sensor_light", "Light Sensor", "sensor", "digital"
            )
        }

        self.relay = DigitalReplica(
            "actuator_relay", "Irrigation Relay", "actuator", "ON/OFF"
        )

    def update_measurement(self, topic, value):
        replica = self.replicas.get(topic)
        if replica is not None:
            replica.update(value)
            return replica
        return None

    def update_relay(self, state):
        self.relay.update(1 if state == "ON" else 0)
        self.relay.value = state

    def get_all(self):
        result = {
            key: replica.to_dict()
            for key, replica in self.replicas.items()
        }
        result["farm/relay/status"] = self.relay.to_dict()
        return result