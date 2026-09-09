import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/trigger_github_workflow.sh"
FAKE_GH = '''#!/usr/bin/python3
import datetime, json, os, pathlib, sys
root = pathlib.Path(os.environ["FAKE_GH_DIR"])
args = sys.argv[1:]
with (root / "calls").open("a") as stream:
    stream.write(json.dumps(args) + "\\n")
fixture = json.loads((root / "fixture").read_text())
if fixture.get("offline"):
    print("test network failure", file=sys.stderr)
    sys.exit(1)
if fixture.get("transient") and not (root / "retried").exists():
    (root / "retried").touch()
    sys.exit(1)
endpoint = next(arg for arg in args if arg.startswith("repos/"))
if endpoint.endswith("/enable"):
    (root / "enabled").touch()
elif endpoint.endswith("/dispatches"):
    pass
elif "/runs?" in endpoint:
    if fixture.get("malformed"):
        print('{"unexpected": []}')
    else:
        today = datetime.datetime.now(datetime.timezone.utc)
        when = today - datetime.timedelta(days=fixture.get("age_days", 0))
        runs = [] if fixture.get("conclusion") is None else [{
            "created_at": "invalid" if fixture.get("invalid_date") else when.isoformat(),
            "status": fixture.get("run_status", "completed"),
            "conclusion": fixture["conclusion"],
        }]
        print(json.dumps({"workflow_runs": runs}))
else:
    print("active" if (root / "enabled").exists() else fixture.get("state", "active"))
'''


class FallbackTest(unittest.TestCase):
    def invoke(self, **fixture):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "gh"
            fake.write_text(FAKE_GH)
            fake.chmod(0o700)
            (root / "fixture").write_text(json.dumps(fixture))
            result = subprocess.run(
                ["/bin/zsh", str(SCRIPT)],
                env={**os.environ, "GLADOS_GH_BIN": str(fake), "FAKE_GH_DIR": directory},
                capture_output=True, text=True, timeout=20,
            )
            calls = [json.loads(line) for line in (root / "calls").read_text().splitlines()]
            return result, calls

    def mutations(self, calls):
        return [call for call in calls if "--method" in call]

    def test_inactivity_is_reenabled_then_dispatched(self):
        result, calls = self.invoke(state="disabled_inactivity")
        self.assertEqual(result.returncode, 0, result.stderr)
        mutations = self.mutations(calls)
        self.assertEqual(len(mutations), 2)
        self.assertIn("PUT", mutations[0])
        self.assertIn("POST", mutations[1])

    def test_manual_disable_is_preserved(self):
        result, calls = self.invoke(state="disabled_manually")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.mutations(calls), [])

    def test_today_success_and_pending_are_skipped(self):
        for conclusion, run_status in (("success", "completed"), ("", "queued")):
            with self.subTest(run_status=run_status):
                result, calls = self.invoke(conclusion=conclusion, run_status=run_status)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.mutations(calls), [])

    def test_failed_or_previous_day_runs_allow_dispatch(self):
        for fixture in ({"conclusion": "failure"}, {"conclusion": "success", "age_days": 1}):
            with self.subTest(fixture=fixture):
                result, calls = self.invoke(**fixture)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(self.mutations(calls)), 1)
                self.assertIn("POST", self.mutations(calls)[0])

    def test_transient_read_failure_is_retried(self):
        result, calls = self.invoke(transient=True, conclusion="success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("attempt 1/3 failed", result.stderr)
        self.assertEqual(self.mutations(calls), [])

    def test_offline_does_not_claim_success(self):
        result, calls = self.invoke(offline=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.mutations(calls), [])

    def test_invalid_run_data_does_not_dispatch(self):
        for fixture in ({"malformed": True}, {"invalid_date": True, "conclusion": "success"}):
            with self.subTest(fixture=fixture):
                result, calls = self.invoke(**fixture)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.mutations(calls), [])


if __name__ == "__main__":
    unittest.main()
