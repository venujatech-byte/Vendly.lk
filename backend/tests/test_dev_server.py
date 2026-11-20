from pathlib import Path
from runpy import run_path
from unittest.mock import Mock

from flask import Flask


def test_lan_server_keeps_reload_without_enabling_debugger(monkeypatch):
    # Exercise Flask's real option handling with an offline listener and no local dotenv.
    app = Flask(__name__)
    app.config["DEBUG"] = True
    listener = Mock()
    monkeypatch.setattr("app.create_app", lambda: app)
    monkeypatch.setattr("werkzeug.serving.run_simple", listener)
    monkeypatch.setenv("FLASK_SKIP_DOTENV", "1")
    monkeypatch.delenv("FLASK_RUN_FROM_CLI", raising=False)
    monkeypatch.setenv("PORT", "5050")

    run_path(str(Path(__file__).resolve().parents[1] / "run.py"), run_name="__main__")

    listener.assert_called_once()
    assert listener.call_args.args[:2] == ("0.0.0.0", 5050)
    assert listener.call_args.kwargs["use_reloader"] is True
    assert listener.call_args.kwargs["use_debugger"] is False
