import json

import pytest

import reranker_engine
from reranker_engine import RerankerEngine


class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class _FakeClient:
    def __init__(self, response_body, captured, **_kwargs):
        self.response_body = response_body
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, endpoint, **kwargs):
        self.captured.update({"endpoint": endpoint, **kwargs})
        return _FakeResponse(self.response_body)


def _config(mode="llm"):
    return {
        "dehydration": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "existing-openai-key",
        },
        "reranker": {
            "enabled": True,
            "mode": mode,
            "model": "gpt-4.1-mini",
            "candidate_limit": 20,
        },
    }


@pytest.mark.asyncio
async def test_llm_reranker_reuses_openai_key_and_returns_ranked_results(monkeypatch):
    captured = {}
    response_body = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "results": [
                                {"index": 1, "score": 0.94},
                                {"index": 0, "score": 0.18},
                            ]
                        }
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(
        reranker_engine.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(response_body, captured, **kwargs),
    )
    engine = RerankerEngine(_config())

    results = await engine.rerank("海边的信", ["购物清单", "清晨写来的信"])

    assert engine.mode == "llm"
    assert engine.candidate_limit == 8
    assert captured["endpoint"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer existing-openai-key"
    assert results[0].index == 1
    assert results[0].score == pytest.approx(0.94)


@pytest.mark.asyncio
async def test_llm_reranker_falls_back_when_json_is_invalid(monkeypatch):
    captured = {}
    response_body = {"choices": [{"message": {"content": "not json"}}]}
    monkeypatch.setattr(
        reranker_engine.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(response_body, captured, **kwargs),
    )
    engine = RerankerEngine(_config())

    assert await engine.rerank("query", ["first", "second"]) == []


@pytest.mark.asyncio
async def test_api_mode_keeps_dedicated_rerank_contract(monkeypatch):
    captured = {}
    response_body = {
        "results": [
            {"index": 0, "relevance_score": 0.8},
            {"index": 1, "relevance_score": 0.2},
        ]
    }
    monkeypatch.setattr(
        reranker_engine.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(response_body, captured, **kwargs),
    )
    config = _config(mode="api")
    config["reranker"]["model"] = "Qwen/Qwen3-Reranker-4B"
    engine = RerankerEngine(config)

    results = await engine.rerank("query", ["first", "second"])

    assert captured["endpoint"] == "https://api.openai.com/v1/rerank"
    assert results[0].index == 0
