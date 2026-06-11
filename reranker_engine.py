from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("ombre_brain.reranker")


@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float


class RerankerEngine:
    """Rerank candidates with a dedicated endpoint or an OpenAI-compatible LLM."""

    def __init__(self, config: dict):
        config = config or {}
        embed_cfg = config.get("embedding", {}) or {}
        rerank_cfg = config.get("reranker", {}) or {}
        dehy_cfg = config.get("dehydration", {}) or {}

        self.mode = str(rerank_cfg.get("mode") or "api").strip().lower()
        if self.mode not in {"api", "llm"}:
            self.mode = "api"
        default_model = "gpt-4.1-mini" if self.mode == "llm" else "Qwen/Qwen3-Reranker-4B"
        self.model = str(rerank_cfg.get("model") or default_model)
        self.base_url = str(
            rerank_cfg.get("base_url")
            or embed_cfg.get("base_url")
            or dehy_cfg.get("base_url")
            or ""
        ).rstrip("/")
        self.api_key = str(
            rerank_cfg.get("api_key")
            or embed_cfg.get("api_key")
            or dehy_cfg.get("api_key")
            or ""
        )
        self.enabled = bool(self.api_key and self.base_url) and _bool_value(
            rerank_cfg.get("enabled", True)
        )
        self.timeout = _float_between(rerank_cfg.get("timeout_seconds", 12), 12, 1, 120)
        self.candidate_limit = _int_between(rerank_cfg.get("candidate_limit", 20), 20, 1, 100)
        if self.mode == "llm":
            self.candidate_limit = min(self.candidate_limit, 8)
        self.score_weight = _float_between(rerank_cfg.get("score_weight", 0.65), 0.65, 0.0, 1.0)

    async def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list[RerankResult]:
        if not self.enabled or not query or len(documents) < 2:
            return []
        if self.mode == "llm":
            return await self._rerank_with_llm(query, documents, top_n)
        return await self._rerank_with_api(query, documents, top_n)

    async def _rerank_with_api(
        self,
        query: str,
        documents: list[str],
        top_n: int | None,
    ) -> list[RerankResult]:
        endpoint = f"{self.base_url}/rerank"
        payload: dict[str, Any] = {
            "model": self.model,
            "query": str(query),
            "documents": [str(document or "") for document in documents],
            "return_documents": False,
        }
        if top_n is not None:
            payload["top_n"] = max(1, min(int(top_n), len(documents)))

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            logger.warning("Reranker request failed: %s", exc)
            return []

        results = []
        for item in body.get("results", []) if isinstance(body, dict) else []:
            try:
                index = int(item.get("index"))
                score = float(item.get("relevance_score", 0.0))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(documents):
                results.append(RerankResult(index=index, score=max(0.0, min(1.0, score))))
        results.sort(key=lambda item: item.score, reverse=True)
        return results

    async def _rerank_with_llm(
        self,
        query: str,
        documents: list[str],
        top_n: int | None,
    ) -> list[RerankResult]:
        endpoint = f"{self.base_url}/chat/completions"
        document_payload = [
            {"index": index, "text": str(document or "")[:1200]}
            for index, document in enumerate(documents)
        ]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You rank memory excerpts for relevance to a recall query. "
                        "Return JSON only, with this shape: "
                        '{"results":[{"index":0,"score":0.95}]}. '
                        "Include every supplied index exactly once. Scores must be "
                        "numbers from 0 to 1. Do not rewrite or summarize memories."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"query": str(query), "documents": document_payload},
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": max(180, min(700, len(documents) * 45)),
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = _parse_json_content(content)
        except Exception as exc:
            logger.warning("LLM reranker request failed: %s", exc)
            return []

        seen: dict[int, float] = {}
        for item in parsed.get("results", []):
            if not isinstance(item, dict):
                continue
            try:
                index = int(item.get("index"))
                score = float(item.get("score"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(documents):
                seen[index] = max(0.0, min(1.0, score))

        if not seen:
            return []

        results = [
            RerankResult(index=index, score=seen.get(index, 0.0))
            for index in range(len(documents))
        ]
        results.sort(key=lambda item: item.score, reverse=True)
        if top_n is not None:
            results = results[: max(1, int(top_n))]
        return results


def _parse_json_content(content: Any) -> dict[str, Any]:
    text = str(content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM reranker response must be a JSON object")
    return parsed


def _bool_value(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _int_between(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(min_value, min(max_value, number))


def _float_between(value: Any, default: float, min_value: float, max_value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(min_value, min(max_value, number))
