import os

import pytest
from fastapi.testclient import TestClient
from server import Job, app


def test_rejects_paths_that_escape_sandbox():
    for path in ["../escape.py", "/etc/evil.py", "foo\\escape.py", "module.sh"]:
        with pytest.raises(ValueError):
            Job(
                feature_title="Test",
                test_module_code="def test_ok(): assert True",
                implementation_files={path: "pass"},
            )


def test_requires_configured_runner_token(monkeypatch):
    monkeypatch.setenv("AI_RUNNER_TOKEN", "secret")
    with TestClient(app) as client:
        result = client.post(
            "/execute",
            json={"feature_title": "Test", "test_module_code": "def test_ok(): assert True"},
        )
        assert result.status_code == 401


def test_real_networkless_sandbox(monkeypatch):
    if os.environ.get("STRIDE_TEST_RUNNER") != "1":
        pytest.skip("Requires built sandbox image and a dedicated Docker test host")
    monkeypatch.setenv("AI_RUNNER_TOKEN", "secret")
    with TestClient(app) as client:
        result = client.post(
            "/execute",
            headers={"Authorization": "Bearer secret"},
            json={
                "feature_title": "Add two integers",
                "implementation_files": {
                    "maths.py": "def add(a: int, b: int) -> int:\n    return a + b\n"
                },
                "test_module_code": "from generated.maths import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            },
        )
        assert result.status_code == 200, result.text
        data = result.json()
        assert data["execution_status"] == "completed", data
        assert data["passed"] is True, data
        assert data["tests_executed"] == 1
        assert data["tests_passed"] == 1
        assert data["coverage_percent"] == 100
