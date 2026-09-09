import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

import glados


class CheckinTest(unittest.TestCase):
    def run_checkin(self, message=glados.ALREADY_RECORDED, cookies="test-cookie", status=None):
        status = status if status is not None else {"data": {"email": "private@example.test", "leftDays": "315.4"}}
        responses = [Mock(status_code=200), Mock(status_code=200)]
        responses[0].json.return_value = status
        responses[1].json.return_value = {"message": message}
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            env = {"GLADOS_COOKIE": cookies, "PUSHPLUS_TOKEN": "", "GITHUB_STEP_SUMMARY": str(summary)}
            with patch.dict(os.environ, env), patch("glados.requests.request", side_effect=responses) as request:
                with contextlib.redirect_stdout(output):
                    result = glados.main()
            return result, output.getvalue(), summary.read_text(), request

    def test_points_are_confirmed_without_leaking_email_or_cookie(self):
        result, output, summary, request = self.run_checkin(message="Checkin! Got 12 Points")
        self.assertEqual(result, 0)
        self.assertIn("earned 12 points", output)
        self.assertIn("CHECKIN_CONFIRMED date=", summary)
        self.assertNotIn("private@example.test", output + summary)
        self.assertNotIn("test-cookie", output + summary)
        for call in request.call_args_list:
            self.assertEqual(call.kwargs["timeout"], (10, 20))
            self.assertFalse(call.kwargs["allow_redirects"])

    def test_already_recorded_is_not_reported_as_new_points(self):
        result, output, summary, _ = self.run_checkin()
        self.assertEqual(result, 0)
        self.assertIn("no new points reported", output)
        self.assertIn("CHECKIN_CONFIRMED", summary)

    def test_missing_cookie_is_failure_without_requests(self):
        result, output, summary, request = self.run_checkin(cookies="")
        self.assertEqual(result, 1)
        request.assert_not_called()
        self.assertNotIn("CHECKIN_CONFIRMED", summary)

    def test_invalid_login_is_failure_without_checkin_post(self):
        result, output, _, request = self.run_checkin(status={"message": "login required"})
        self.assertEqual(result, 1)
        self.assertIn("Login could not be verified", output)
        self.assertEqual(request.call_count, 1)

    def test_unknown_messages_are_not_false_success(self):
        for message in ("cookie expired", "Service temporarily unavailable", "success", None):
            with self.subTest(message=message):
                result, output, summary, _ = self.run_checkin(message=message)
                self.assertEqual(result, 1)
                self.assertNotIn("CHECKIN_CONFIRMED", output + summary)

    def test_network_and_http_errors_fail_without_leaking_exception_text(self):
        with patch("glados.requests.request", side_effect=requests.Timeout("cookie-secret")):
            with self.assertRaisesRegex(glados.CheckinError, "Request failed: Timeout") as caught:
                glados.checkin("cookie-secret")
            self.assertNotIn("cookie-secret", str(caught.exception))
        with patch("glados.requests.request", return_value=Mock(status_code=403)):
            with self.assertRaisesRegex(glados.CheckinError, "HTTP 403"):
                glados.checkin("cookie-secret")

    def test_invalid_json_is_failure(self):
        response = Mock(status_code=200)
        response.json.side_effect = ValueError("sensitive response body")
        with patch("glados.requests.request", return_value=response):
            with self.assertRaisesRegex(glados.CheckinError, "did not return JSON"):
                glados.checkin("cookie-secret")

    def test_one_failed_account_fails_the_whole_run(self):
        with patch.dict(os.environ, {"GLADOS_COOKIE": "first&second", "PUSHPLUS_TOKEN": "", "GITHUB_STEP_SUMMARY": ""}):
            with patch("glados.checkin", side_effect=["earned 12 points", glados.CheckinError("invalid cookie")]):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(glados.main(), 1)
                self.assertIn("Account 2: FAILED", output.getvalue())
                self.assertNotIn("CHECKIN_CONFIRMED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
