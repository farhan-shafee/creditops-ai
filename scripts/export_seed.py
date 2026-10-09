"""Publish the deterministic fictional fixtures as reviewable JSON and Markdown."""

import json

from creditops.business_seed import make_business_seed
from creditops.seed import make_seed
from creditops.settings import PROJECT_ROOT


def export():
    fixture = make_seed()
    business = make_business_seed()
    directories = {
        "incidents": fixture["incidents"],
        "business": business,
        "logs": [r for r in fixture["evidence"] if r["kind"] == "log"],
        "metrics": [r for r in fixture["evidence"] if r["kind"] == "metric"],
        "topology": {"services": fixture["services"], "dependencies": fixture["dependencies"]},
        "telemetry": [
            r
            for r in fixture["evidence"]
            if r["kind"] in {"kafka", "fix", "database", "deployment", "history"}
        ],
    }
    for directory, records in directories.items():
        path = PROJECT_ROOT / "data" / directory / "synthetic.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    for record in fixture["evidence"]:
        if record["kind"] == "runbook":
            path = PROJECT_ROOT / "data" / "runbooks" / f"{record['id']}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(record["data"]["content"], encoding="utf-8")


if __name__ == "__main__":
    export()
