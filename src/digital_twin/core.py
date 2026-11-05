from datetime import datetime
import sys

from src.virtualization.digital_replica import DigitalReplicaManager
from src.virtualization.digital_replica.course_framework import (
    CourseFrameworkAdapter,
    load_framework_class,
    FRAMEWORK_ROOT,
)


# Load the course framework's BaseService first.
FrameworkBaseService = load_framework_class(
    "course_base_service",
    FRAMEWORK_ROOT / "src" / "services" / "base.py",
    "BaseService",
)

# Register it under the import path expected by the original framework.
import types

services_module = sys.modules.get("src.services")
if services_module is None:
    services_module = types.ModuleType("src.services")
    services_module.__path__ = [
        str(FRAMEWORK_ROOT / "src" / "services")
    ]
    sys.modules["src.services"] = services_module

base_module = types.ModuleType("src.services.base")
base_module.BaseService = FrameworkBaseService
sys.modules["src.services.base"] = base_module


# Load the original course DigitalTwin.
FrameworkDigitalTwin = load_framework_class(
    "course_digital_twin",
    FRAMEWORK_ROOT / "src" / "digital_twin" / "core.py",
    "DigitalTwin",
)


class SmartFarmDigitalTwin:
    """Coordinates SmartFarm replicas and the original course DigitalTwin."""

    def __init__(self):
        self.twin_id = "smartfarm_001"
        self.name = "Smart Farm Digital Twin"
        self.created_at = datetime.now().isoformat(timespec="seconds")

        self.replicas = DigitalReplicaManager()

        self.framework_adapter = CourseFrameworkAdapter()
        self.framework_twin = FrameworkDigitalTwin()
        self.framework_replicas = {}

        definitions = {
            "farm/temperature": ("sensor", "Temperature Sensor", "sensor", "°C"),
            "farm/humidity": ("sensor", "Humidity Sensor", "sensor", "%"),
            "farm/moisture": ("sensor", "Soil Moisture Sensor", "sensor", "%"),
            "farm/light": ("sensor", "Light Sensor", "sensor", "digital"),
            "farm/relay/status": ("actuator", "Irrigation Relay", "actuator", "ON/OFF"),
        }

        for topic, (replica_type, name, component_type, unit) in definitions.items():
            replica = self.framework_adapter.create_replica(
                replica_type=replica_type,
                name=name,
                component_type=component_type,
                unit=unit,
                value=0.0,
                status="OFF" if component_type == "actuator" else "initializing",
            )

            self.framework_replicas[topic] = replica
            self.framework_twin.add_digital_replica(replica)

    def _update_framework_replica(self, topic, value, status=None):
        replica = self.framework_replicas.get(topic)
        if replica is None:
            return

        replica["data"]["value"] = float(value)
        replica["data"]["last_updated"] = datetime.now().isoformat()
        replica["metadata"]["updated_at"] = datetime.now()

        if status is not None:
            replica["data"]["status"] = str(status)

    def process_measurement(self, topic, value):
        result = self.replicas.update_measurement(topic, value)
        self._update_framework_replica(topic, value, "active")
        return result

    def process_relay_status(self, state):
        self.replicas.update_relay(state)
        value = 1.0 if str(state).upper() == "ON" else 0.0
        self._update_framework_replica(
            "farm/relay/status", value, str(state).upper()
        )

    def get_state(self):
        return {
            "twin_id": self.twin_id,
            "name": self.name,
            "created_at": self.created_at,
            "replicas": self.replicas.get_all(),
        }


digital_twin = SmartFarmDigitalTwin()
