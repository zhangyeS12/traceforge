from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from traceforge.core import run_command
from traceforge.storage import connect, get_file_changes, init_workspace


class GitAttributionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="traceforge-test-")).resolve()
        self.git = shutil.which("git")
        if not self.git:
            self.skipTest("git is required")
        self._run_git("init")
        self._run_git("config", "user.name", "TraceForge Tests")
        self._run_git("config", "user.email", "tests@example.invalid")
        (self.root / "a.py").write_text('print("a v1")\n', encoding="utf-8")
        (self.root / "b.py").write_text('print("b v1")\n', encoding="utf-8")
        self._run_git("add", ".")
        self._run_git("commit", "-m", "init")
        init_workspace(self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.git, *args],
            cwd=self.root,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def _changes_for(self, run_id: str) -> list[tuple[str, str]]:
        paths = init_workspace(self.root)
        with connect(paths) as conn:
            return [(row["status"], row["path"]) for row in get_file_changes(conn, run_id)]

    def test_preexisting_dirty_file_is_not_attributed_to_run(self) -> None:
        (self.root / "a.py").write_text('print("a dirty before run")\n', encoding="utf-8")
        (self.root / "modify_b.py").write_text(
            'from pathlib import Path\nPath("b.py").write_text(\'print("b changed by run")\\n\', encoding="utf-8")\n',
            encoding="utf-8",
        )

        result = run_command([sys.executable, "modify_b.py"], cwd=self.root)
        changes = self._changes_for(result.run_id)
        changed_paths = {path for _, path in changes}
        patch = result.patch_path.read_text(encoding="utf-8", errors="replace")

        self.assertIn("b.py", changed_paths)
        self.assertNotIn("a.py", changed_paths)
        self.assertIn('b changed by run', patch)
        self.assertNotIn('a dirty before run', patch)

    def test_run_change_to_preexisting_dirty_file_is_attributed(self) -> None:
        (self.root / "a.py").write_text('print("a dirty before run")\n', encoding="utf-8")
        (self.root / "modify_a.py").write_text(
            'from pathlib import Path\nPath("a.py").write_text(\'print("a changed during run")\\n\', encoding="utf-8")\n',
            encoding="utf-8",
        )

        result = run_command([sys.executable, "modify_a.py"], cwd=self.root)
        changes = self._changes_for(result.run_id)
        patch = result.patch_path.read_text(encoding="utf-8", errors="replace")

        self.assertIn(("M", "a.py"), changes)
        self.assertIn('a dirty before run', patch)
        self.assertIn('a changed during run', patch)

    def test_untracked_new_file_content_is_in_patch(self) -> None:
        (self.root / "create_new.py").write_text(
            'from pathlib import Path\nPath("new_agent_file.py").write_text(\'print("new file content")\\n\', encoding="utf-8")\n',
            encoding="utf-8",
        )

        result = run_command([sys.executable, "create_new.py"], cwd=self.root)
        changes = self._changes_for(result.run_id)
        patch = result.patch_path.read_text(encoding="utf-8", errors="replace")

        self.assertIn(("??", "new_agent_file.py"), changes)
        self.assertIn("new file mode", patch)
        self.assertIn("new_agent_file.py", patch)
        self.assertIn('print("new file content")', patch)

    def test_tracked_file_changed_to_binary_is_not_reported_as_deleted(self) -> None:
        (self.root / "make_binary.py").write_text(
            'from pathlib import Path\nPath("a.py").write_bytes(b"\\x00\\x01traceforge-binary")\n',
            encoding="utf-8",
        )

        result = run_command([sys.executable, "make_binary.py"], cwd=self.root)
        changes = self._changes_for(result.run_id)
        patch = result.patch_path.read_text(encoding="utf-8", errors="replace")

        self.assertIn(("M", "a.py"), changes)
        self.assertIn("could not capture textual content", patch)
        self.assertIn("reason=binary", patch)
        self.assertNotIn("deleted file mode", patch)


if __name__ == "__main__":
    unittest.main()
