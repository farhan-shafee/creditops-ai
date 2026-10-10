"""Keyless launch settings are isolated from the owner's dotenv file."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def settings_process(env_file: str, *, forbid_dotenv: bool = False) -> dict:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADMIN_API_KEY"}
    }
    environment.update(
        CREDITOPS_ENV_FILE=env_file,
        PUBLIC_DEMO="true",
        EMBEDDINGS_ENABLED="false",
        REPLAY_DIR=str(ROOT / "data" / "showcase"),
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        PYTHONPATH=os.pathsep.join((str(ROOT / "apps" / "api"), str(ROOT / "apps" / "mcp"))),
    )
    setup = (
        "from pathlib import Path\n"
        "from pydantic_settings.sources import DotEnvSettingsSource\n"
        "original_read = DotEnvSettingsSource._read_env_file\n"
        f"allowed_file = {env_file!r}\n"
        f"forbid_dotenv = {forbid_dotenv!r}\n"
        "def guarded_read(self, file_path):\n"
        "    if forbid_dotenv or Path(file_path) != Path(allowed_file):\n"
        "        raise AssertionError('unapproved dotenv read attempted')\n"
        "    return original_read(self, file_path)\n"
        "DotEnvSettingsSource._read_env_file = guarded_read\n"
    )
    script = setup + (
        "import json\n"
        "from creditops.settings import Settings\n"
        "config = Settings()\n"
        "print(json.dumps({\n"
        "    'keys_absent': all(value is None for value in (config.openai_api_key, config.anthropic_api_key, config.admin_api_key)),\n"
        "    'openai_canary_loaded': config.openai_api_key is not None and config.openai_api_key.get_secret_value() == 'offline-canary-not-a-real-key',\n"
        "    'public_demo': config.public_demo,\n"
        "    'embeddings_enabled': config.embeddings_enabled,\n"
        "    'replay_dir': str(config.replay_dir),\n"
        "}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=environment, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def test_empty_env_file_disables_all_dotenv_reads():
    result = settings_process("", forbid_dotenv=True)
    assert result["keys_absent"] is True
    assert result["public_demo"] is True
    assert result["embeddings_enabled"] is False
    assert Path(result["replay_dir"]) == ROOT / "data" / "showcase"


def test_explicit_isolated_dotenv_accepts_fake_canary_without_owner_file(tmp_path):
    dotenv = tmp_path / "isolated-canary.env"
    dotenv.write_text("OPENAI_API_KEY=offline-canary-not-a-real-key\n", encoding="utf-8")
    assert settings_process(str(dotenv))["openai_canary_loaded"] is True


def test_default_dotenv_path_remains_unchanged():
    environment = {key: value for key, value in os.environ.items() if key != "CREDITOPS_ENV_FILE"}
    environment["PYTHONPATH"] = str(ROOT / "apps" / "api")
    result = subprocess.run(
        [sys.executable, "-c", "from creditops.settings import Settings; print(Settings.model_config['env_file'])"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert Path(result.stdout.strip()) == ROOT / ".env"
