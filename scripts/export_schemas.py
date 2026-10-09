"""Export reviewable cross-language runtime contracts from the API models."""

import json
from pathlib import Path

from creditops.models import Assessment, BusinessImpact, Evidence, Incident, Instrument, Investigation

directory = Path(__file__).resolve().parents[1] / "packages" / "schemas"
directory.mkdir(parents=True, exist_ok=True)
models = (Evidence, Incident, Investigation, Assessment, Instrument, BusinessImpact)
for model in models:
    path = directory / f"{model.__name__.lower()}.schema.json"
    path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Exported {len(models)} Pydantic JSON schemas")
