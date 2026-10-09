"""Prepare or explicitly execute a finite paid-provider verification.

Default is a credential-free dry run. This command was not executed with
--execute-paid during the second pass; offline mocks are separate test receipts.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from creditops.investigator import collect_adaptive_investigation
from creditops.providers import create_provider
from creditops.settings import Settings
from creditops.store import Store


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai", "anthropic"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--case-count", type=int, choices=range(1, 4), required=True)
    parser.add_argument("--max-tool-calls", type=int, choices=range(2, 17), required=True)
    parser.add_argument("--max-provider-turns", type=int, choices=range(2, 17), required=True)
    parser.add_argument("--max-spend-usd", type=float, required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument(
        "--execute-paid",
        action="store_true",
        help="Explicitly authorize bounded paid requests; absence means dry-run",
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/live-verification/latest.json"))
    args = parser.parse_args(argv)
    if (
        not args.model.strip()
        or len(args.model) > 120
        or not 0 < args.max_spend_usd <= 10
        or not 1 <= args.timeout_seconds <= 300
    ):
        parser.error(
            "Explicit model, positive spend cap <= $10 and timeout between 1 and 300 seconds are required"
        )
    return args


async def run(args):
    receipt = {
        "execution": "NOT RUN",
        "quality": "UNVERIFIED",
        "provider": args.provider,
        "model": args.model,
        "case_count": args.case_count,
        "max_tool_calls_per_case": args.max_tool_calls,
        "max_provider_turns_per_case": args.max_provider_turns,
        "maximum_spend_usd": args.max_spend_usd,
        "timeout_seconds_per_case": args.timeout_seconds,
        "transport": "mcp_stdio",
        "results": [],
        "limitation": "Requires a running local API using the same database and server-side credentials plus positive provider input/output price ceilings. Price ceilings must cover the chosen model's actual rates. No automatic retries, no embeddings. Reservations use serialized input bytes plus 16KiB overhead and the full 5000-token output cap; unused reservations are not refunded.",
    }
    if not args.execute_paid:
        print(json.dumps(receipt, indent=2))
        return receipt
    os.environ[f"{args.provider.upper()}_MODEL"] = args.model
    configuration = Settings(
        max_diagnostic_calls=args.max_tool_calls,
        max_provider_turns=args.max_provider_turns,
        investigation_timeout_seconds=args.timeout_seconds,
    )
    provider = create_provider(args.provider)
    store = None
    try:
        provider.enable_budget(args.max_spend_usd)  # one reservation ledger across all cases
        store = Store()
        await store.initialize()
        session_id = str(uuid4())
        for index in range(1, args.case_count + 1):
            incident_id = f"INC-DEMO-{index:03d}"
            await store.activate_case(session_id, incident_id)
            async with asyncio.timeout(args.timeout_seconds):
                result = await collect_adaptive_investigation(
                    store, session_id, incident_id, provider, limits=configuration
                )
            receipt["results"].append(result)
        receipt["execution"] = "COMPLETED_PAID_REQUESTS"
        receipt["quality"] = "UNVERIFIED_SMALL_SYNTHETIC_SAMPLE"
    except Exception as error:
        receipt["execution"] = "STOPPED"
        receipt["error"] = type(error).__name__  # credentials/internal messages never printed
        raise
    finally:
        receipt["reserved_spend_usd"] = str(getattr(provider, "_reserved_spend", "0"))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        await provider.client.close()
        if store:
            await store.close()
    print(json.dumps({key: value for key, value in receipt.items() if key != "results"}, indent=2))
    return receipt


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
