"""Actual orchestrator, software gateway fixtures; no positive robot claim."""

import json

import pytest
from cascade.agent.llm import LLMClient, LLMResponse, ToolCall
from test_agent_domain import FixtureGateway

from microduck_workshop.agent.runner import build_agent, local_endpoint


class RecordingFixtureLLM(LLMClient):
    def __init__(self):
        self.requests = []

    def chat(self, system, messages, tools=None, max_tokens=1024):
        self.requests.append(str(messages))
        calls = [
            ToolCall("microduck.observe", {}, "a"),
            ToolCall("microduck.walk_bounded", dict(vx=0.05, vy=0, wz=0, duration_s=0.2), "b"),
            ToolCall("microduck.verify", {}, "c"),
            ToolCall("task_done", dict(success=True, summary="fixture overclaims"), "d"),
        ]
        return LLMResponse(tool_calls=[calls[len(self.requests) - 1]])


def test_actual_orchestrator_does_not_promote_fixture_failure(tmp_path):
    llm = RecordingFixtureLLM()
    agent, runtime = build_agent(
        llm,
        FixtureGateway(),
        tmp_path,
        episode_id="episode-1",
        frame_id="microduck_camera_optical",
        max_steps=4,
    )
    try:
        report = agent.run_task("Read the detector, walk once only on GO, verify.")
        assert report.success is False
        assert [row["tool"] for row in report.tool_log] == [
            "microduck.observe",
            "microduck.walk_bounded",
            "microduck.verify",
            "task_done",
        ]
        assert "SECRET" not in str(llm.requests)
        assert "world_pose" not in str(llm.requests)
        assert len(llm.requests) == 4
        assert agent.decompose is False
        assert agent.attach_images is False
        specs = {s["name"]: s for s in runtime.tool_specs}
        assert specs["microduck.observe"]["parameters"]["required"] == []
        assert '"action":"observe"' in runtime.system_prompt
        assert (tmp_path / "trace.jsonl").is_file()
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://10.0.0.1:8080/v1",
        "http://localhost.evil:18510/v1",
        "http://u:p@127.0.0.1:18510/v1",
    ],
)
def test_remote_or_credentialed_endpoint_refused(url):
    with pytest.raises(ValueError):
        local_endpoint(url)


def test_task_done_cannot_claim_motion_without_any_action(tmp_path):
    class Overclaim(LLMClient):
        def chat(self, **kwargs):
            return LLMResponse(
                tool_calls=[ToolCall("task_done", dict(success=True, summary="walked"), "a")]
            )

    agent, runtime = build_agent(
        Overclaim(),
        FixtureGateway(),
        tmp_path,
        episode_id="episode-1",
        frame_id="microduck_camera_optical",
        max_steps=1,
    )
    try:
        assert agent.run_task("Walk once").success is False
    finally:
        runtime.close()


def test_actual_openai_adapter_records_exact_safe_request_without_headers(tmp_path):
    import httpx
    from openai import OpenAI

    from microduck_workshop.agent.runner import RecordedLocalClient

    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "fixture",
                "object": "chat.completion",
                "created": 1,
                "model": "qwen3.8-27b",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "x",
                                    "type": "function",
                                    "function": {"name": "microduck.observe", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
            },
        )

    path = tmp_path / "provider.jsonl"
    client = RecordedLocalClient(
        model="qwen3.8-27b", base_url="http://127.0.0.1:18510/v1", transcript=path, max_requests=1
    )
    client._client.close()
    client._client = OpenAI(
        base_url="http://127.0.0.1:18510/v1",
        api_key="SECRET_AUTH",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    try:
        response = client.chat(
            "test",
            [
                {
                    "role": "tool",
                    "tool_call_id": "a",
                    "content": json.dumps(
                        {
                            "ok": True,
                            "world_pose": [99, 99, 99],
                            "verified": False,
                            "reason": "gateway_verdict",
                        }
                    ),
                }
            ],
            tools=[
                {
                    "name": "microduck.observe",
                    "description": "Observe",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                }
            ],
        )
        assert response.tool_calls[0].name == "microduck.observe"
        with pytest.raises(RuntimeError):
            client.chat("test", [])
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(captured) == 1
        assert captured[0]["tool_choice"] == "required"
        assert len(records) == 2
        assert "world_pose" not in path.read_text()
        assert "SECRET_AUTH" not in path.read_text()
        assert records[0]["body"]["messages"] == captured[0]["messages"]
    finally:
        client.close()


def test_local_client_ignores_proxy_environment(tmp_path, monkeypatch):
    from microduck_workshop.agent.runner import RecordedLocalClient

    monkeypatch.setenv("HTTP_PROXY", "http://untrusted-proxy.invalid:3128")
    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted-proxy.invalid:3128")
    client = RecordedLocalClient(
        model="qwen3.8-27b",
        base_url="http://127.0.0.1:18510/v1",
        transcript=tmp_path / "proxy.jsonl",
    )
    try:
        assert client._client._client.follow_redirects is False
        assert client._client._client._mounts == {}
    finally:
        client.close()
