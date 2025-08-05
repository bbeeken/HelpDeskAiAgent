import json
import requests
import sys
from typing import Set

# Expected tool names exposed by the server
EXPECTED_TOOLS: Set[str] = {
    "get_ticket",
    "create_ticket",
    "update_ticket",
    "bulk_update_tickets",
    "add_ticket_message",
    "get_ticket_messages",
    "get_ticket_attachments",
    "search_tickets",
    "get_analytics",
    "get_reference_data",
    "get_ticket_full_context",
    "advanced_search",
    "get_system_snapshot",
    "get_ticket_stats",
    "get_workload_analytics",
    "sla_metrics",
}


def verify(base_url: str, *, allow_superset: bool = False) -> bool:
    """Fetch `/tools` and verify the available tool names.

    Parameters
    ----------
    base_url:
        Base URL of the server to query.
    allow_superset:
        If True, do not treat unexpected additional tools as an error.
    """
    url = base_url.rstrip('/') + '/tools'
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    tools = data["tools"]

    reported = {t["name"] for t in tools}

    missing = EXPECTED_TOOLS - reported
    unexpected = set() if allow_superset else reported - EXPECTED_TOOLS

    ok = True

    if missing:
        print("Missing tools:", ", ".join(sorted(missing)))
        ok = False
    if unexpected:
        print("Unexpected tools:", ", ".join(sorted(unexpected)))
        ok = False

    if ok:
        print("All expected tools present.")
    else:
        print("Server tool list:")
        print(json.dumps(tools, indent=2))
    return ok


def main(argv: list[str]) -> int:
    base_url = argv[1] if len(argv) > 1 else "http://localhost:8000"
    allow_superset = "--allow-superset" in argv
    try:
        success = verify(base_url, allow_superset=allow_superset)
    except Exception as exc:
        print(f"Verification failed: {exc}")
        return 1
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
