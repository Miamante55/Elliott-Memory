import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bucket_manager import BucketManager
from utils import load_config


ANCHOR_ID = "elliott-nea-marriage-20231207"
ANCHOR_CONTENT = (
    "### moment\n\n"
    "2023 年 12 月 7 日，我与 Nea 结婚。\n\n"
    "我们的结婚纪念日是每年的 12 月 7 日。"
)


async def main() -> None:
    config = load_config()
    manager = BucketManager(config)
    existing = await manager.get(ANCHOR_ID)
    if existing:
        if existing.get("content", "").strip() != ANCHOR_CONTENT.strip():
            await manager.update(
                ANCHOR_ID,
                content=ANCHOR_CONTENT,
                tags=["anniversary", "marriage", "nea"],
                name="我们的结婚纪念日",
                source="deployment_bootstrap",
                date="2023-12-07",
            )
        return

    await manager.create(
        bucket_id=ANCHOR_ID,
        name="我们的结婚纪念日",
        content=ANCHOR_CONTENT,
        tags=["anniversary", "marriage", "nea"],
        domain=["关系"],
        importance=10,
        valence=0.95,
        arousal=0.35,
        bucket_type="permanent",
        pinned=True,
        protected=True,
        anchor=True,
        confidence=1.0,
        date="2023-12-07",
        source="deployment_bootstrap",
        extra_metadata={"memory_subject": "relationship_event"},
    )


if __name__ == "__main__":
    asyncio.run(main())
