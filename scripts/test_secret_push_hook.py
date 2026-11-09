"""Offline tests for the local fail-closed pre-push secret scanner.

A fake Gitleaks CLI exercises hook control flow, not real secret detection.
The GitHub Actions Gitleaks step performs the actual detection check.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-push"


class PrePushHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name)
        self.repo = home / "working"
        self.bare = home / "remote.git"
        self.repo.mkdir()
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Hook Test")
        self._git("config", "user.email", "hook@example.invalid")
        (self.repo / "sample.txt").write_text("initial\n", encoding="utf-8")
        self._git("add", "sample.txt")
        self._git("commit", "-m", "initial")
        subprocess.run(["git", "init", "--bare", str(self.bare)],
                       check=True, capture_output=True, text=True)
        self._git("remote", "add", "origin", str(self.bare))
        self._git("push", "--no-verify", "-u", "origin", "main")
        self.old_remote = self._bare_rev("refs/heads/main")

        hooks = self.repo / ".githooks"
        hooks.mkdir()
        shutil.copy2(HOOK, hooks / "pre-push")
        (hooks / "pre-push").chmod(0o755)
        self._git("config", "--local", "core.hooksPath", ".githooks")

        self.bin_dir = home / "bin"
        self.bin_dir.mkdir()
        self.log_file = home / "gitleaks.log"
        fake = self.bin_dir / "gitleaks"
        fake.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$*" >> "$GITLEAKS_TEST_LOG"\n'
            'exit "$GITLEAKS_TEST_EXIT"\n',
            encoding="utf-8",
        )
        fake.chmod(0o755)
        self.env = os.environ.copy()
        self.env["PATH"] = str(self.bin_dir) + os.pathsep + self.env.get("PATH", "")
        self.env["GITLEAKS_TEST_LOG"] = str(self.log_file)
        self.env["GITLEAKS_TEST_EXIT"] = "0"

        (self.repo / "sample.txt").write_text("new change\n", encoding="utf-8")
        self._git("add", "sample.txt")
        self._git("commit", "-m", "new commit")

    def _git(self, *args: str, env: dict | None = None, check: bool = True):
        return subprocess.run(
            ["git", *args], cwd=self.repo, env=env,
            check=check, capture_output=True, text=True,
        )

    def _bare_rev(self, ref: str) -> str:
        return subprocess.run(
            ["git", "--git-dir", str(self.bare), "rev-parse", ref],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def test_clean_push_scans_new_commits(self) -> None:
        result = self._git("push", "origin", "main", env=self.env)
        self.assertIn("Scanning commits", result.stderr)
        self.assertIn(self.old_remote + "..", self.log_file.read_text(encoding="utf-8"))
        self.assertEqual(self._bare_rev("refs/heads/main"),
                         self._git("rev-parse", "HEAD").stdout.strip())

    def test_gitleaks_finding_blocks_remote_push(self) -> None:
        self.env["GITLEAKS_TEST_EXIT"] = "1"
        result = self._git("push", "origin", "main", env=self.env, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Secret scan BLOCKED", result.stderr)
        self.assertEqual(self._bare_rev("refs/heads/main"), self.old_remote)

    def test_new_branch_scans_only_unpushed_commits(self) -> None:
        self._git("checkout", "-b", "feature")
        self._git("push", "origin", "feature", env=self.env)
        args = self.log_file.read_text(encoding="utf-8")
        self.assertIn("--not --remotes=origin", args)
        self.assertEqual(self._bare_rev("refs/heads/feature"),
                         self._git("rev-parse", "HEAD").stdout.strip())

    def test_ref_deletion_does_not_invoke_gitleaks(self) -> None:
        result = subprocess.run(
            ["sh", str(HOOK), "origin", str(self.bare)],
            cwd=self.repo, env=self.env, text=True, capture_output=True,
            input="refs/heads/deleted " + ("0" * 40) +
                  " refs/heads/deleted " + self.old_remote + "\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.log_file.exists())


if __name__ == "__main__":
    unittest.main()
