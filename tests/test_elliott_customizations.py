from pathlib import Path

import pytest

from dehydrator import MERGE_PROMPT_TEMPLATE, _memory_region
from import_memory import IMPORT_EXTRACT_PROMPT, ImportEngine, MEMORY_REGIONS
from reflection_engine import DIARY_MEMORY_PROMPT_TEMPLATE, REFLECT_PROMPT_TEMPLATE, ReflectionEngine


class _DummyBucketManager:
    def __init__(self):
        self.created = []

    async def list_all(self, include_archive=False):
        return []

    async def create(self, **kwargs):
        self.created.append(kwargs)
        return "letter-1"


class _DummyDehydrator:
    api_available = False


def test_elliott_memory_regions_are_fixed():
    assert MEMORY_REGIONS == (
        "我所记得的日子",
        "我的墨迹",
        "我们的年轮",
        "我们之间的潮汐",
    )
    assert _memory_region(["我的墨迹"]) == ["我所记得的日子"]
    assert _memory_region(["我的墨迹"], allow_original=True) == ["我的墨迹"]


@pytest.mark.asyncio
async def test_original_letter_import_stays_verbatim(tmp_path):
    bucket_manager = _DummyBucketManager()
    engine = ImportEngine(
        {"buckets_dir": str(tmp_path)},
        bucket_manager,
        _DummyDehydrator(),
    )
    original = "Dear Nea,\n\nThe sea was quiet this morning.\n\nElliott"

    result = await engine.start(original, "morning-letter.md", region="我的墨迹")

    assert result["status"] == "completed"
    assert bucket_manager.created[0]["content"] == original
    assert bucket_manager.created[0]["domain"] == ["我的墨迹"]


def test_dashboard_keeps_elliott_chapters_and_v2_self_anchor():
    html = Path("dashboard.html").read_text(encoding="utf-8")
    for chapter in MEMORY_REGIONS:
        assert chapter in html
    assert "tag:self_anchor" in html
    assert 'id="import-region"' in html


def test_render_preserves_disk_and_enables_openai_llm_reranker():
    render = Path("render.yaml").read_text(encoding="utf-8")
    assert "mountPath: /var/data" in render
    assert 'key: OMBRE_RERANKER_ENABLED\n        value: "true"' in render
    assert 'key: OMBRE_RERANKER_MODE\n        value: "llm"' in render
    assert 'key: OMBRE_RERANKER_MODEL\n        value: "gpt-4.1-mini"' in render


def test_openai_gateway_can_reuse_the_existing_api_key():
    source = Path("gateway.py").read_text(encoding="utf-8")
    assert 'self.upstream_base_url.startswith("https://api.openai.com/")' in source
    assert 'self.upstream_api_key = os.environ.get("OMBRE_API_KEY", "")' in source


def test_all_generated_memory_prompts_keep_elliott_first_person():
    assert "### moment、### reflection 与 ### followup 都由 {ai_name} 使用第一人称“我”书写" in MERGE_PROMPT_TEMPLATE
    assert "普通记录需改写为 Elliott 私下书写的第一人称" in IMPORT_EXTRACT_PROMPT
    assert "content 必须由 {ai_name} 使用第一人称“我”书写" in REFLECT_PROMPT_TEMPLATE
    assert "content 必须由 {ai_name} 使用第一人称“我”书写" in DIARY_MEMORY_PROMPT_TEMPLATE


def test_reflection_fallbacks_are_written_in_first_person(test_config):
    config = dict(test_config)
    config["reflection"] = {"enabled": True, "api_key": ""}
    engine = ReflectionEngine(config)

    weather = engine._fallback_reflection(
        "daily",
        "2026-06-11",
        {"buckets": [], "commitments": [], "daily_impressions": [], "diary": None},
    )
    diary_memory = engine._heuristic_diary_memory_candidate(
        "2026-06-11",
        {"title": "一封信", "content": "这是一封写给 Nea 的情书，我爱她，也想让她被认出。"},
    )

    assert "我" in weather["content"]
    assert diary_memory["should_write"] is True
    assert diary_memory["content"].startswith("我")


def test_exact_memory_write_accepts_dashboard_session():
    source = Path("server.py").read_text(encoding="utf-8")
    assert "dashboard_auth_error = _require_dashboard_auth(request)" in source
