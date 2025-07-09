import requests
import sys
from typing import Dict, Set

# Expected mapping of tool categories to tool names
EXPECTED_TOOLS: Dict[str, Set[str]] = {
    "ticket": {"get_ticket"},
    "analytics": {"ticket_count"},
    "ai": {"ai_echo"},
}


def verify(base_url: str) -> bool:
    """Fetch `/tools` and verify the available tool names."""
    url = base_url.rstrip('/') + '/tools'
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    tools = data["tools"]

    reported = {t["name"] for t in tools}
    expected = set().union(*EXPECTED_TOOLS.values())

    missing = expected - reported
    unexpected = reported - expected

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
