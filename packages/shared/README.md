# Shared domain contract

The cross-language product vocabulary is specified in `docs/API_CONTRACT.md` and exported JSON schemas in `packages/schemas`. Backend Pydantic models own runtime validation; the Next.js API client owns typed browser consumption. Stable evidence IDs connect the two without serializing hidden evaluation labels.

Synthetic client/order/session naming, diagnostic allowlists, the simulated clock and disclaimer are intentional domain constraints. Agents have no infrastructure mutation capability. The MCP server uses the same read-only API facade as the investigator.
