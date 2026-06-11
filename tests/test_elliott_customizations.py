from pathlib import Path

import pytest

from dehydrator import _memory_region
from import_memory import ImportEngine, MEMORY_REGIONS


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


def test_render_preserves_disk_and_disables_unconfigured_reranker():
    render = Path("render.yaml").read_text(encoding="utf-8")
    assert "mountPath: /var/data" in render
    assert "OMBRE_RERANKER_ENABLED" in render
    assert 'value: "false"' in render
