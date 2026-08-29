"""Gate 1 uses the LLM when available and falls back to heuristics otherwise."""

import pytest
from httpx import AsyncClient
from src.services import ai_pipeline_service


@pytest.mark.asyncio
async def test_gate1_uses_llm_output_when_available(client: AsyncClient, make_tenant, monkeypatch):
    t = await make_tenant("ai-llm@test.io", key="AIL")

    async def fake_complete_json(system, user):
        return {
            "feature_title": "Bulk CSV Export",
            "suggested_priority": "HIGH",
            "estimated_points": 8,
            "acceptance_criteria": [
                "Given a manager on the reports page",
                "When they click Export CSV",
                "Then a CSV of the filtered rows downloads",
            ],
            "ambiguity_score": 0.1,
        }

    monkeypatch.setattr(ai_pipeline_service, "complete_json", fake_complete_json)

    r = await client.post(
        "/api/v1/ai/pipeline/gate1-intent",
        json={"project_id": t["project"]["id"], "feature_prompt": "please add csv export"},
        headers=t["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["feature_title"] == "Bulk CSV Export"
    assert body["suggested_priority"] == "HIGH"
    assert body["estimated_points"] == 8
    assert body["passed"] is True


@pytest.mark.asyncio
async def test_gate1_falls_back_to_heuristic_when_llm_unavailable(
    client: AsyncClient, make_tenant, monkeypatch
):
    t = await make_tenant("ai-heur@test.io", key="AIH")

    async def no_llm(system, user):
        return None  # simulates every provider failing / unset

    monkeypatch.setattr(ai_pipeline_service, "complete_json", no_llm)

    r = await client.post(
        "/api/v1/ai/pipeline/gate1-intent",
        json={
            "project_id": t["project"]["id"],
            "feature_prompt": "urgent: fix the broken login redirect loop",
        },
        headers=t["headers"],
    )
    assert r.status_code == 200
    # Heuristic keyword path picks up "urgent".
    assert r.json()["suggested_priority"] == "URGENT"
