import requests
import sys
from typing import Set

# Expected tool names exposed by the server
EXPECTED_TOOLS: Set[str] = {
    "g_ticket",
    "l_tickets",
}


def verify(base_url: str) -> bool:
    """Fetch `/tools` and verify the available tool names."""
    url = base_url.rstrip('/') + '/tools'
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    tools = data["tools"]

    reported = {t["name"] for t in tools}

    missing = EXPECTED_TOOLS - reported
    unexpected = reported - EXPECTED_TOOLS

    ok = True

    if missing:
        print("Missing tools:", ", ".join(sorted(missing)))
        ok = False
    if unexpected:
        print("Unexpected tools:", ", ".join(sorted(unexpected)))
        ok = False

    if ok:
        print("All expected tools present.")
    return ok


def main(argv: list[str]) -> int:
    base_url = argv[1] if len(argv) > 1 else "http://localhost:8000"
    try:
        success = verify(base_url)
    except Exception as exc:
        print(f"Verification failed: {exc}")
        return 1
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
