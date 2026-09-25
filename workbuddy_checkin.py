#!/usr/bin/env python3
"""WorkBuddy daily check-in via the official client API."""
import os
import sys
import time
from datetime import datetime, timezone

import requests

BASE = "https://copilot.tencent.com"
STATUS_URL = f"{BASE}/v2/billing/meter/checkin-activity-status"
CHECKIN_URL = f"{BASE}/v2/billing/meter/daily-checkin"
TIMEOUT = 20
RETRIES = 3


def request_json(url: str, token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "WorkBuddy-Checkin/1.1",
    }
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json={}, timeout=TIMEOUT)
            try:
                data = response.json()
            except ValueError:
                raise RuntimeError(
                    f"HTTP {response.status_code}: non-JSON response: {response.text[:200]}"
                )

            # WorkBuddy may return business errors using HTTP 4xx. Preserve
            # the JSON body so callers can distinguish 10001 (already signed).
            if response.status_code >= 500 and attempt < RETRIES:
                time.sleep(2 * attempt)
                continue
            return response.status_code, data
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt < RETRIES:
                time.sleep(2 * attempt)
            else:
                raise RuntimeError(f"Request failed after {RETRIES} attempts: {exc}") from exc

    raise RuntimeError(f"Request failed: {last_error}")


def main():
    token = os.environ.get("WORKBUDDY_TOKEN", "").strip()
    if not token:
        print("WORKBUDDY_TOKEN is not configured.")
        return 2

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"WorkBuddy check-in started: {now}")

    status_http, status = request_json(STATUS_URL, token)
    print(f"Status API: HTTP {status_http}")

    if status.get("code") not in (0, None):
        print(f"Status API business response: {status}")

    status_data = status.get("data") or {}
    # Do not rely solely on today_checked_in: current clients have observed
    # that this field can be stale. daily-checkin code 10001 is authoritative.
    if status_data.get("today_checked_in") is True:
        print("Already checked in today (status API).")
        return 0

    checkin_http, result = request_json(CHECKIN_URL, token)
    code = result.get("code")
    print(f"Check-in API: HTTP {checkin_http}, code={code}")

    if code == 0:
        data = result.get("data") or {}
        points = data.get("credit", data.get("daily_credit", data.get("points", "unknown")))
        streak = data.get("streak_days", data.get("continuous_days", "unknown"))
        print(f"Check-in succeeded. points={points} streak_days={streak}")
        return 0

    if code == 10001:
        print("Already checked in today (API code 10001).")
        return 0

    if checkin_http in (401, 403):
        print("Check-in failed: token is invalid, expired, or unauthorized.")
    else:
        print(f"Check-in failed: {result}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
