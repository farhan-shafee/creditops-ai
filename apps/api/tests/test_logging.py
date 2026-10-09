"""Structured logging must emit safe context, without leaking injected credentials."""

import io
import json
import logging

from creditops.main import JSONLogFormatter


def test_json_logging_redacts_secrets_and_preserves_diagnostic_fields():
    record = logging.LogRecord(
        "creditops.http", logging.INFO, "", 0, "api_key=synthetic-credential", (), None
    )
    record.tool = "search_logs"
    record.incident_id = "INC-DEMO-001"
    payload = json.loads(JSONLogFormatter().format(record))
    assert "synthetic-credential" not in json.dumps(payload)
    assert payload["tool"] == "search_logs"
    assert payload["incident_id"] == "INC-DEMO-001"


def test_repeated_logging_configuration_emits_one_json_record(monkeypatch):
    from creditops import main

    configure = getattr(main, "configure_logging", None)
    assert configure is not None, "Application has not configured structured log emission"
    configure()
    configure()
    logger = logging.getLogger("creditops")
    configured = [handler for handler in logger.handlers if isinstance(handler.formatter, JSONLogFormatter)]
    assert len(configured) == 1
    stream = io.StringIO()
    monkeypatch.setattr(configured[0], "stream", stream)
    logging.getLogger("creditops.http").info("request_completed", extra={"method": "GET", "status": 200})
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["status"] == 200
