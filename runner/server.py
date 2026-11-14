"""Dedicated execution host. Do not expose publicly or co-locate with production data."""

import asyncio
import json
import os
import secrets
from typing import Annotated

import docker
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

app = FastAPI(docs_url=None, redoc_url=None)
limit = asyncio.Semaphore(int(os.environ.get("RUNNER_CONCURRENCY", "2")))


class Job(BaseModel):
    feature_title: str = Field(max_length=1000)
    test_module_code: str = Field(max_length=100000)
    implementation_files: dict[str, str] = Field(default_factory=dict, max_length=30)

    @model_validator(mode="after")
    def bounded(self):
        if sum(len(k) + len(v) for k, v in self.implementation_files.items()) > 50000:
            raise ValueError("Generated implementation exceeds 50KB")
        if len(self.model_dump_json().encode()) > 120000:
            raise ValueError("Job exceeds sandbox input limit")
        for path in self.implementation_files:
            if (
                path.startswith("/")
                or "\\" in path
                or ".." in path.split("/")
                or not path.endswith(".py")
            ):
                raise ValueError("Only relative Python module paths are accepted")
        return self


def execute(job):
    client = docker.from_env(timeout=65)
    container = None
    try:
        container = client.containers.run(
            os.environ.get("RUNNER_SANDBOX_IMAGE", "stride-ai-sandbox:local"),
            detach=True,
            network_disabled=True,
            read_only=True,
            mem_limit="256m",
            nano_cpus=1000000000,
            pids_limit=64,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            user="65534:65534",
            tmpfs={
                "/work": "rw,nosuid,size=64m,mode=1777",
                "/tmp": "rw,noexec,nosuid,size=32m,mode=1777",
            },
            environment={
                "STRIDE_JOB": job.model_dump_json(),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            log_config=docker.types.LogConfig(
                type="json-file", config={"max-size": "1m", "max-file": "1"}
            ),
        )
        result = container.wait(timeout=60)
        if result["StatusCode"] != 0:
            raise RuntimeError("Sandbox exited unsuccessfully")
        logs = container.logs(tail=1)
        if len(logs) > 10000:
            raise RuntimeError("Sandbox output exceeded limit")
        return json.loads(logs)
    finally:
        if container is not None:
            container.remove(force=True)
        client.close()


@app.post("/execute")
async def execute_job(job: Job, authorization: Annotated[str | None, Header()] = None):
    token = os.environ.get("AI_RUNNER_TOKEN", "")
    if not token or not secrets.compare_digest(authorization or "", "Bearer " + token):
        raise HTTPException(401, "Runner authentication required")
    if limit.locked():
        raise HTTPException(429, "Execution capacity reached; retry later")
    async with limit:
        try:
            return await asyncio.to_thread(execute, job)
        except Exception:
            return {
                "passed": False,
                "static_analysis_passed": False,
                "tests_executed": 0,
                "tests_passed": 0,
                "coverage_percent": None,
                "execution_status": "runner_failed",
                "summary": "Isolated execution could not complete",
            }
