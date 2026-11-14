"""Exercise real API requests through a non-owner, non-superuser Postgres role."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_postgres_rls_api_isolation():
    url = os.environ.get("STRIDE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Requires a disposable migrated Postgres database")
    backend = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DATABASE_URL": url, "ENVIRONMENT": "test"}
    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    script = r"""
import asyncio, uuid
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import settings
from src.core.database import get_db_session
from src.main import create_app
from src.core.redis import close_redis

async def run():
    admin = create_async_engine(settings.DATABASE_URL)
    role = 'stride_rls_' + uuid.uuid4().hex
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS'))
        await conn.execute(text(f'GRANT USAGE ON SCHEMA public TO {role}'))
        await conn.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}'))
    runtime = create_async_engine(settings.DATABASE_URL)
    @event.listens_for(runtime.sync_engine, 'connect')
    def assume_role(connection, record):
        cursor=connection.cursor(); cursor.execute(f'SET ROLE {role}'); cursor.close()
    factory=async_sessionmaker(runtime,expire_on_commit=False)
    app=create_app()
    async def dependency():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise
    app.dependency_overrides[get_db_session]=dependency
    try:
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            async def tenant(suffix):
                response=await client.post('/api/v1/auth/register',json={'email':f'{role}-{suffix}@example.com','password':'Password12345!','full_name':'RLS Test'})
                assert response.status_code==201,response.text
                tokens=response.json()['data']['tokens']
                h={'Authorization':'Bearer '+tokens['access_token']}
                org=(await client.get('/api/v1/organizations',headers=h)).json()[0]['id']
                h['X-Org-ID']=org
                spaces=await client.get(f'/api/v1/organizations/{org}/workspaces',headers=h)
                assert spaces.status_code==200,spaces.text
                project=await client.post('/api/v1/projects',headers=h,json={'workspace_id':spaces.json()[0]['id'],'name':'RLS project','key':'RLS'})
                assert project.status_code==201,project.text
                task=await client.post('/api/v1/tasks',headers=h,json={'project_id':project.json()['id'],'title':suffix})
                assert task.status_code==201,task.text
                return org,task.json(),h
            a,ta,ha=await tenant('a'); b,tb,hb=await tenant('b')
            # Deliberately omit org filters in raw SQL to prove database enforcement.
            async with factory() as db:
                assert (await db.execute(text('SELECT id FROM tasks'))).all()==[]
                await db.execute(text("SELECT set_config('stride.org_id', :org, true)"),{'org':a})
                ids=(await db.execute(text('SELECT id FROM tasks'))).scalars().all()
                assert ta['id'] in ids and tb['id'] not in ids,ids
                changed=await db.execute(text('UPDATE tasks SET title=\'intrusion\' WHERE id=:id'),{'id':tb['id']})
                assert changed.rowcount==0
                await db.rollback()
            # Pool reuse and the next transaction must not retain tenant A's scope.
            async with factory() as db:
                assert (await db.execute(text('SELECT id FROM tasks'))).all()==[]
            response=await client.get('/api/v1/tasks/'+tb['id'],headers=ha)
            assert response.status_code==404,response.text
            response=await client.get('/api/v1/tasks/'+ta['id'],headers=ha)
            assert response.status_code==200,response.text
    finally:
        await close_redis()
        await runtime.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP OWNED BY {role}'))
            await conn.execute(text(f'DROP ROLE {role}'))
        await admin.dispose()
asyncio.run(run())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
