"""Generate reproducible evaluation and persisted replay artifacts."""

import argparse
import asyncio
import json

from creditops.evaluation import run_evaluations
from creditops.store import Store


async def main(provider: str) -> None:
    store = Store()
    await store.initialize()
    try:
        artifact = await run_evaluations(store, provider)
        print(json.dumps({key: artifact[key] for key in ("generated_at", "case_count", "live_ai_status")}))
        for algorithm in artifact["algorithms"]:
            print(json.dumps({key: value for key, value in algorithm.items() if key != "results"}))
    finally:
        await store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider", choices=["deterministic", "openai", "anthropic"], default="deterministic"
    )
    args = parser.parse_args()
    if args.provider != "deterministic":
        parser.error(
            "This command preserves the offline 15-case evaluation. Use the bounded live-verification command with explicit provider/model, case/turn/call limits and approved spend for a separately authorized provider run."
        )
    asyncio.run(main(args.provider))
