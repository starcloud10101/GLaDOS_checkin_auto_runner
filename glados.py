import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import requests


ORIGIN = "https://glados.cloud"
TAIPEI = timezone(timedelta(hours=8))
ALREADY_RECORDED = "Today's observation logged. Return tomorrow for more points."


class CheckinError(Exception):
    pass


def request_json(method, path, cookie, **kwargs):
    try:
        response = requests.request(
            method,
            ORIGIN + path,
            headers={
                "cookie": cookie,
                "referer": ORIGIN + "/console/checkin",
                "origin": ORIGIN,
                "user-agent": "Mozilla/5.0",
            },
            timeout=(10, 20),
            allow_redirects=False,
            **kwargs,
        )
    except requests.RequestException as error:
        # Exception text can contain request headers or URLs with secrets.
        raise CheckinError("Request failed: " + type(error).__name__) from None
    if response.status_code != 200:
        raise CheckinError("GLaDOS returned HTTP " + str(response.status_code))
    try:
        payload = response.json()
    except ValueError:
        raise CheckinError("GLaDOS did not return JSON") from None
    if not isinstance(payload, dict):
        raise CheckinError("Unexpected GLaDOS response format")
    return payload


def checkin(cookie):
    status = request_json("GET", "/api/user/status", cookie)
    data = status.get("data")
    if not isinstance(data, dict) or not data.get("email"):
        raise CheckinError("Login could not be verified; check GLADOS_COOKIE")
    try:
        days = Decimal(str(data["leftDays"]))
        if not days.is_finite():
            raise ValueError("non-finite days")
        days = int(days)
    except (KeyError, InvalidOperation, ValueError, OverflowError):
        raise CheckinError("Account status is missing valid remaining days") from None

    result = request_json("POST", "/api/user/checkin", cookie, json={"token": "glados.one"})
    message = result.get("message", "")
    if not isinstance(message, str):
        raise CheckinError("Check-in response has no valid message")
    message = message.strip()
    earned = re.fullmatch(r"Checkin! Got ([0-9]+) Points", message, flags=re.IGNORECASE)
    if earned:
        outcome = "earned " + earned.group(1) + " points"
    elif message.casefold() == ALREADY_RECORDED.casefold():
        outcome = "already recorded today (no new points reported)"
    else:
        raise CheckinError("Unrecognized check-in result; success is not confirmed")
    return outcome + "; account status before check-in: " + str(days) + " days remaining"


def main():
    cookies = [value.strip() for value in os.environ.get("GLADOS_COOKIE", "").split("&") if value.strip()]
    lines = []
    failed = not cookies
    if not cookies:
        lines.append("FAILED: GLADOS_COOKIE is missing")
    for index, cookie in enumerate(cookies, start=1):
        try:
            lines.append("Account " + str(index) + ": CONFIRMED, " + checkin(cookie))
        except CheckinError as error:
            failed = True
            lines.append("Account " + str(index) + ": FAILED, " + str(error))

    if not failed:
        day = datetime.now(TAIPEI).date().isoformat()
        lines.append("CHECKIN_CONFIRMED date=" + day + " accounts=" + str(len(cookies)))
    for line in lines:
        print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("## GLaDOS check-in\n\n" + "\n\n".join(lines) + "\n")

    pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "")
    if pushplus_token:
        try:
            notification = requests.post(
                "https://www.pushplus.plus/send",
                json={"token": pushplus_token, "title": "GLaDOS check-in", "content": "\n".join(lines)},
                timeout=(10, 20),
            )
            notification.raise_for_status()
        except requests.RequestException:
            print("WARNING: PushPlus delivery failed; see Actions for the check-in result")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
