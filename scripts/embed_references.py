"""Explicit opt-in indexing of synthetic reference content using configured official embeddings."""

import asyncio

from creditops.embeddings import index_references
from creditops.store import Store


async def main():
    store = Store()
    try:
        await store.initialize()
        count = await index_references(store)
        print(f"Indexed {count} synthetic reference documents")
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
