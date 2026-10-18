"""Exercise installed command behavior from outside the repository directory."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "recorded_episode"


class PackageCommandTests(unittest.TestCase):
    def invoke(self, cwd, *arguments):
        return subprocess.run([sys.executable, "-m", "agent_vla", *map(str, arguments)],
                              cwd=cwd, capture_output=True, text=True)

    def test_replay_outside_checkout_preserves_diagnostic_scope(self):
        with TemporaryDirectory() as directory:
            result = self.invoke(directory, "replay", FIXTURE)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["primary_acceptance_evidence"])
        self.assertEqual(report["replay_outcome"]["steps"], 2)
        self.assertFalse(report["replay_outcome"]["success"])

    def test_timeline_refuses_to_overwrite_research_output(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "timeline.html"
            first = self.invoke(directory, "timeline", FIXTURE, output)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = output.read_bytes()
            self.assertIn(b"Recorded decisions", original)
            second = self.invoke(directory, "timeline", FIXTURE, output)
            self.assertEqual(second.returncode, 1)
            self.assertEqual(output.read_bytes(), original)

    def test_invalid_trace_is_an_actionable_error(self):
        with TemporaryDirectory() as directory:
            result = self.invoke(directory, "replay", directory)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid replay bundle", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_observation_interface_does_not_import_execution(self):
        with TemporaryDirectory() as directory:
            result = subprocess.run([
                sys.executable, "-c",
                "import sys; from agent_vla.observations.contracts import ObservationIngestor; "
                "assert ObservationIngestor('episode'); "
                "assert 'agent_vla.runtime.harness' not in sys.modules; "
                "assert 'torch' not in sys.modules; assert 'numpy' not in sys.modules",
            ], cwd=directory, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
