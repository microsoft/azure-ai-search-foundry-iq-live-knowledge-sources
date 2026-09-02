import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LiveksWrapperTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "The POSIX launcher is covered by the Ubuntu command contract.")
    def test_try_bypasses_an_incomplete_virtual_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            venv = Path(temp_dir)
            python = venv / "bin" / "python"
            python.parent.mkdir()
            python.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
            python.chmod(0o755)

            env = os.environ.copy()
            env["LIVEKS_VENV"] = str(venv)
            result = subprocess.run(
                [str(ROOT / "liveks"), "try", "--format", "json"],
                cwd="/",
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"mode": "offline-replay"', result.stdout)

    @unittest.skipIf(os.name == "nt", "The POSIX launcher is covered by the Ubuntu command contract.")
    def test_relative_virtual_environment_override_is_root_relative(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            venv = Path(temp_dir)
            python = venv / "bin" / "python"
            python.parent.mkdir()
            python.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            python.chmod(0o755)

            env = os.environ.copy()
            env["LIVEKS_VENV"] = os.path.relpath(venv, ROOT)
            result = subprocess.run(
                [str(ROOT / "liveks"), "profiles", "--format", "json"],
                cwd="/",
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            ["-m", "liveks.cli", "profiles", "--format", "json"],
        )


if __name__ == "__main__":
    unittest.main()
