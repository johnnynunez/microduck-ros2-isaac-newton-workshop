"""Verify upstream signatures/pin, not just an importable package named cascade."""

from microduck_workshop.agent.api_check import check_cascade_api


def test_pinned_cascade_api_has_full_domain_and_bounded_llm_contract():
    report = check_cascade_api()
    assert report["ok"] is True
    assert report["pin"] == "d7a456c22d46d53e9588db6a55a0c6c916aa4963"
    assert report["classes"]["AgentOrchestrator"]["decompose"] is True
    assert "max_retries" in report["classes"]["OpenAICompatClient"]
    assert report["source_verified"] is True
