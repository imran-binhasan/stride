"""Validate deployed DDL on an isolated local Postgres, when binaries are available."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def test_postgres_migrations_and_schema():
    configured_url = os.environ.get("STRIDE_TEST_POSTGRES_URL")
    if configured_url:
        backend = Path(__file__).resolve().parents[2]
        env = {**os.environ, "DATABASE_URL": configured_url}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        check_migrated_schema(backend, env)
        return
    bindir = Path("/usr/lib/postgresql/18/bin")
    if not (bindir / "initdb").exists() or os.geteuid() == 0:
        pytest.skip("Local non-root Postgres binaries are unavailable")
    backend = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="stride-pg-") as directory:
        root = Path(directory)
        data, sockets = root / "data", root / "socket"
        sockets.mkdir()
        initialized = subprocess.run(
            [str(bindir / "initdb"), "-D", str(data), "-U", "stride", "-A", "trust", "--no-locale"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert initialized.returncode == 0, initialized.stderr
        started = False
        try:
            result = subprocess.run(
                [
                    str(bindir / "pg_ctl"),
                    "-D",
                    str(data),
                    "-l",
                    str(root / "server.log"),
                    "-o",
                    f"-h '' -k {sockets}",
                    "-w",
                    "start",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, result.stderr + (root / "server.log").read_text()
            started = True
            env = {
                **os.environ,
                "DATABASE_URL": f"postgresql+asyncpg://stride@/postgres?host={sockets}",
            }
            migrated = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=backend,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert migrated.returncode == 0, migrated.stdout + migrated.stderr
            check_migrated_schema(backend, env)
        finally:
            if started:
                subprocess.run(
                    [str(bindir / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"],
                    capture_output=True,
                    timeout=20,
                )


def check_migrated_schema(backend, env):
    """Check every mapped table and column for both CI and local Postgres."""
    script = """import asyncio
from sqlalchemy import inspect
from src.core.database import engine
from src.models import auth, project, task, time_tracking, integrations, hr, client, billing, notifications
from src.models.base import Base
async def run():
    async with engine.connect() as conn:
        def check(sync_conn):
            inspector = inspect(sync_conn)
            for table in Base.metadata.sorted_tables:
                actual = {c['name'] for c in inspector.get_columns(table.name)}
                assert set(table.c.keys()) <= actual, (table.name, set(table.c.keys()) - actual)
        await conn.run_sync(check)
    await engine.dispose()
asyncio.run(run())"""
    checked = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
