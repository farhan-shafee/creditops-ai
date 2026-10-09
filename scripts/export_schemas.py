"""Export reviewable cross-language runtime contracts from the API models."""

import json
from pathlib import Path

from creditops.models import Assessment, Evidence, Incident, Investigation

directory = Path(__file__).resolve().parents[1] / "packages" / "schemas"
directory.mkdir(parents=True, exist_ok=True)
for model in (Evidence, Incident, Investigation, Assessment):
    path = directory / f"{model.__name__.lower()}.schema.json"
    path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("Exported four Pydantic JSON schemas")
