#!/usr/bin/env python3
"""WorkBuddy daily check-in.

The access token is read from the WORKBUDDY_TOKEN environment variable.
"""
import os
import sys
from datetime import datetime, timezone

import requests

BASE = "https://copilot.tencent.com"
STATUS_URL = f"{BASE}/billing/meter/checkin-status"
CHECKIN_URL = f"{BASE}/billing/meter/daily-checkin"
TIMEOUT = 20


def request_json(url: str, token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "WorkBuddy-Checkin/1.0",
    }
    response = requests.post(url, headers=headers, timeout=TIMEOUT)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(f"HTTP {response.status_code}: non-JSON response: {response.text[:200]}")
    if response.status_code not in (200, 400):
        raise RuntimeError(f"HTTP {response.status_code}: {data}")
    return data


def main():
    token = os.environ.get("WORKBUDDY_TOKEN", "").strip()
    if not token:
        print("WORKBUDDY_TOKEN is not configured.")
        return 2

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"WorkBuddy check-in started: {now}")

    status = request_json(STATUS_URL, token)
    if status.get("code") not in (0, None):
        print(f"Status API returned: {status}")

    status_data = status.get("data") or {}
    if status_data.get("today_checked_in") is True:
        print("Already checked in today.")
        return 0

    result = request_json(CHECKIN_URL, token)
    code = result.get("code")

    if code == 0:
        data = result.get("data") or {}
        points = data.get("credit", data.get("daily_credit", data.get("points", "unknown")))
        streak = data.get("streak_days", "")
        print(f"Check-in succeeded. points={points} streak_days={streak}")
        return 0

    if code == 10001:
        print("Already checked in today (API code 10001).")
        return 0

    print(f"Check-in failed: {result}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
