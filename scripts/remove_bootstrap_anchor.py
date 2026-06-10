import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bucket_manager import BucketManager
from utils import load_config


ANCHOR_ID = "elliott-nea-marriage-20231207"


async def main() -> None:
    manager = BucketManager(load_config())
    existing = await manager.get(ANCHOR_ID)
    if existing:
        path = existing.get("path")
        if path and os.path.isfile(path):
            os.remove(path)

    tombstone = os.path.join(manager.tombstone_dir, f"{ANCHOR_ID}.json")
    if os.path.isfile(tombstone):
        os.remove(tombstone)


if __name__ == "__main__":
    asyncio.run(main())
