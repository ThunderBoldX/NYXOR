import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DesktopBackendTests(unittest.TestCase):
    def run_engine(self, directory, actions):
        requests = "".join(json.dumps({"id": str(i), "payload": payload}) + "\n" for i, payload in enumerate(actions))
        command = [os.environ["NYXOR_TEST_ENGINE"]] if os.environ.get("NYXOR_TEST_ENGINE") else [sys.executable, str(ROOT / "desktop/backend.py")]
        result = subprocess.run(command + [directory], input=requests, text=True, encoding="utf-8",
                                capture_output=True, timeout=60, env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([row["id"] for row in rows], [str(i) for i in range(len(actions))])
        return [row["response"] for row in rows]

    def test_private_data_persistence_validation_and_no_login(self):
        with tempfile.TemporaryDirectory(prefix="NYXOR unicode ґ ") as directory:
            responses = self.run_engine(directory, [
                {"action": "snapshot"}, {"action": "queue", "items": ["Rust", "Rust", "Warframe"]},
                {"action": "settings", "values": {"energy_saver": True, "language": "en", "startup_mode": "app"}},
                {"action": "streamers", "items": ["invalid login"]}, {"action": "start"},
                {"action": "exec"}, {"action": "stop"},
            ])
            self.assertEqual(responses[0]["data"]["platform"], "desktop")
            self.assertFalse(responses[0]["data"]["authenticated"])
            self.assertEqual(responses[1]["data"]["queue"], ["Rust", "Warframe"])
            self.assertTrue(responses[2]["data"]["settings"]["energy_saver"])
            self.assertEqual(responses[2]["data"]["settings"]["startup_mode"], "app")
            for index in [3, 4, 5]:
                self.assertFalse(responses[index]["ok"])
            saved = self.run_engine(directory, [{"action": "snapshot"}])[0]["data"]
            self.assertEqual(saved["queue"], ["Rust", "Warframe"])
            self.assertEqual(saved["settings"]["language"], "en")
            self.assertEqual(saved["settings"]["startup_mode"], "app")
            self.assertTrue((Path(directory) / "locales/en.json").exists())


if __name__ == "__main__":
    unittest.main()
