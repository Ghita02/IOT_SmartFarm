from pathlib import Path
import importlib.util


PROJECT_ROOT = Path(__file__).resolve().parents[3]

FRAMEWORK_ROOT = (
    PROJECT_ROOT
    / "external"
    / "InternetOfThings_Architecture_Database_lecture"
)

SCHEMA_PATH = PROJECT_ROOT / "config" / "schemas" / "smartfarm.yaml"


def load_framework_class(module_name, file_path, class_name):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load framework module: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


SchemaRegistry = load_framework_class(
    "course_schema_registry",
    FRAMEWORK_ROOT / "src" / "virtualization" / "digital_replica" / "schema_registry.py",
    "SchemaRegistry",
)

DRFactory = load_framework_class(
    "course_dr_factory",
    FRAMEWORK_ROOT / "src" / "virtualization" / "digital_replica" / "dr_factory.py",
    "DRFactory",
)


class CourseFrameworkAdapter:
    """Adapter around the original course SchemaRegistry and DRFactory."""

    def __init__(self):
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"SmartFarm schema not found: {SCHEMA_PATH}")

        self.schema_registry = SchemaRegistry()
        self.schema_registry.load_schema("smartfarm", str(SCHEMA_PATH))
        self.dr_factory = DRFactory(str(SCHEMA_PATH))

    def create_replica(
        self,
        replica_type,
        name,
        component_type,
        unit,
        value,
        status="active",
    ):
        initial_data = {
            "profile": {
                "name": name,
                "component_type": component_type,
                "unit": unit,
            },
            "data": {
                "value": float(value),
                "status": status,
                "last_updated": "",
            },
        }

        return self.dr_factory.create_dr(replica_type, initial_data)
