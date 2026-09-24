import unittest
from pathlib import Path


CONTROL_ROOT = Path(__file__).resolve().parent.parent


class VerifyAllHydrationTests(unittest.TestCase):
    def test_verify_all_hydrates_canonical_private_runtime_before_legacy_proof(self):
        script = CONTROL_ROOT / "bin" / "logres-verify-all-ref"
        self.assertTrue(script.is_file(), "versioned verify-all helper is required")
        text = script.read_text()

        # Final verification must mirror verify-farm / Android packaging by
        # copying the complete canonical private runtime bundle. Copying only
        # Global/config subtrees is insufficient once visual checkpoints need
        # the playable 002_000_00001 field package.
        self.assertIn('BASE/public/__logres_ref', text)
        self.assertIn('rsync -a "$BASE/public/__logres_ref/" "$WT/public/__logres_ref/"', text)
        self.assertIn('[hydrate] canonical private runtime bundle', text)

        # Keep the independent legacy renderer proof as an additional fixture.
        self.assertIn('--map-id 001_000_00002', text)

        # Required pre-APK visual/runtime files must fail closed if hydration is
        # incomplete rather than silently receiving Vite's SPA fallback.
        for required in (
            "002_000_00001.map.bin",
            "002_000_00001_CHIP.png",
            "002_000_00001_OBJ.png",
            "chip_d.bin",
            "object_d.bin",
        ):
            self.assertIn(required, text)

        self.assertIn("FINAL_GATE missing required playable runtime", text)

    def test_verify_all_serializes_fixed_playwright_port(self):
        script = CONTROL_ROOT / "bin" / "logres-verify-all-ref"
        text = script.read_text()

        self.assertIn(
            "FINAL_VERIFY_LOCK=/home/ubuntu/logres/control/final-verify.lock",
            text,
        )
        self.assertIn(
            'FINAL_VERIFY_LOCK_WAIT_SECONDS="${LOGRES_FINAL_VERIFY_LOCK_WAIT_SECONDS:-900}"',
            text,
        )
        self.assertIn(
            'flock -w "$FINAL_VERIFY_LOCK_WAIT_SECONDS" 9',
            text,
        )
        self.assertIn('E2E_PORT=$(python3 - <<\'PY\'', text)
        self.assertIn(
            's.replace("127.0.0.1:4174", f"127.0.0.1:{port}")',
            text,
        )
        self.assertIn(
            's.replace("--port 4174", f"--port {port}")',
            text,
        )

        lock_pos = text.index('flock -w "$FINAL_VERIFY_LOCK_WAIT_SECONDS" 9')
        worktree_pos = text.index('git -C "$BASE" worktree add')
        verify_pos = text.index('npm run verify:all')
        self.assertLess(lock_pos, worktree_pos)
        self.assertLess(lock_pos, verify_pos)


if __name__ == "__main__":
    unittest.main()
