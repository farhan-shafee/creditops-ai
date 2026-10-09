"""Reset only a specified local synthetic browser session."""

import argparse
import asyncio
from uuid import UUID

from creditops.store import Store


async def reset(session: str):
    store = Store()
    await store.initialize()
    for scenario in await store.scenarios():
        await store.reset_scenario(session, scenario["id"])
    await store.close()
    print("Specified synthetic session reset")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, help="Browser X-Demo-Session UUID")
    args = parser.parse_args()
    asyncio.run(reset(str(UUID(args.session))))
