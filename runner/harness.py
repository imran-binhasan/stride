"""Runs only inside a fresh resource-limited, networkless container."""

import json
import os
import subprocess
from pathlib import Path


def run():
    payload = json.loads(os.environ.pop("STRIDE_JOB"))
    root = Path("/work")
    generated = root / "generated"
    generated.mkdir()
    (generated / "__init__.py").write_text("")
    for name, code in payload.get("implementation_files", {}).items():
        target = generated / name
        if not name.endswith(".py") or not target.resolve().is_relative_to(generated.resolve()):
            raise ValueError("Unsafe implementation path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code)
    (root / "test_generated.py").write_text(payload["test_module_code"])

    def command(args):
        with (root / "command.log").open("wb") as log:
            return subprocess.run(
                args, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=25, check=False
            ).returncode

    lint = command(["ruff", "check", "generated"]) == 0
    typed = command(["mypy", "--strict", "generated"]) == 0
    exit_code = command(
        [
            "pytest",
            "-q",
            "test_generated.py",
            "--json-report",
            "--json-report-file=report.json",
            "--cov=generated",
            "--cov-report=json:coverage.json",
        ]
    )
    report = (
        json.loads((root / "report.json").read_text()) if (root / "report.json").exists() else {}
    )
    summary = report.get("summary", {})
    count = summary.get("total", 0)
    passed = summary.get("passed", 0)
    coverage = (
        json.loads((root / "coverage.json").read_text()).get("totals", {}).get("percent_covered")
        if (root / "coverage.json").exists()
        else None
    )
    static = lint and typed
    success = (
        bool(payload.get("implementation_files"))
        and count > 0
        and passed == count
        and exit_code == 0
        and static
        and (coverage or 0) >= 90
    )
    return {
        "passed": success,
        "static_analysis_passed": static,
        "tests_executed": count,
        "tests_passed": passed,
        "coverage_percent": coverage,
        "execution_status": "completed",
        "summary": f"{passed}/{count} tests passed; lint={lint}; strict types={typed}; measured coverage={coverage}",
    }


if __name__ == "__main__":
    try:
        result = run()
    except Exception as error:
        result = {
            "passed": False,
            "static_analysis_passed": False,
            "tests_executed": 0,
            "tests_passed": 0,
            "coverage_percent": None,
            "execution_status": "runner_failed",
            "summary": f"Sandbox execution failed: {type(error).__name__}",
        }
    print(json.dumps(result), flush=True)
