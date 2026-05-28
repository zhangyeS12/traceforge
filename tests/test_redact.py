from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from traceforge.cli import export_run
from traceforge.core import run_command
from traceforge.redact import REDACTION, redact_text
from traceforge.storage import init_workspace


class RedactionTests(unittest.TestCase):
    def test_redact_text_masks_common_secret_shapes(self) -> None:
        text = (
            "OPENAI_API_KEY=sk-testsecretvalue123456 "
            "Authorization: Bearer abcdefghijklmnop "
            "path=C:\\Users\\alice\\repo"
        )

        redacted = redact_text(text)

        self.assertIn(REDACTION, redacted)
        self.assertNotIn("sk-testsecretvalue123456", redacted)
        self.assertNotIn("abcdefghijklmnop", redacted)
        self.assertNotIn("C:\\Users\\alice", redacted)

    def test_redacted_export_masks_artifacts_and_metadata(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="traceforge-redact-test-")).resolve()
        git = shutil.which("git")
        if not git:
            self.skipTest("git is required")
        try:
            subprocess.run([git, "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run([git, "config", "user.name", "TraceForge Tests"], cwd=root, check=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            (root / "emit_secret.py").write_text(
                "print('OPENAI_API_KEY=sk-testsecretvalue123456')\n",
                encoding="utf-8",
            )
            subprocess.run([git, "add", "."], cwd=root, check=True)
            subprocess.run([git, "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            paths = init_workspace(root)
            result = run_command([sys.executable, "emit_secret.py"], cwd=root)
            out = export_run(paths, result.run_id, redact=True)
            data = json.loads(out.read_text(encoding="utf-8"))
            text = json.dumps(data, ensure_ascii=False)

            self.assertTrue(data["redacted"])
            self.assertIn(REDACTION, text)
            self.assertNotIn("sk-testsecretvalue123456", text)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
