"""Seed immutable synthetic fixtures, without creating active public incidents."""

import asyncio

from creditops.store import seed_database

if __name__ == "__main__":
    asyncio.run(seed_database())
