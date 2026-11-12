"""Docker probe; stdlib only, without bot token or database credentials."""

import os
from urllib.request import urlopen


def main():
    try:
        port = int(os.environ.get("WEBHOOK_PORT", "8080"))
        if not 1 <= port <= 65535:
            return 1
        with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
