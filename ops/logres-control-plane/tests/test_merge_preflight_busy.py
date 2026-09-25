from pathlib import Path
import unittest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "bin"
    / "logres-merge-preflight"
)


class MergePreflightBusyTests(unittest.TestCase):
    def test_gate_busy_is_deferred_not_failed_or_quarantined(self):
        text = SCRIPT.read_text()
        self.assertIn('elif gp.returncode==75:', text)
        self.assertIn('state="DEFERRED_BUSY"', text)
        self.assertIn('PREFLIGHT_DEFERRED_BUSY', text)

        packet_index = text.index('c.commit(); p=packet(c,pid)')
        busy_index = text.index(
            '        if gp.returncode==75:',
            packet_index,
        )
        failure_index = text.index(
            '        if gp.returncode:',
            busy_index + 1,
        )
        regression_index = text.index(
            'logres-regression-capture',
            busy_index,
        )
        quarantine_index = text.index(
            'QUARANTINED after exact-SHA full-e2e',
            busy_index,
        )

        self.assertLess(busy_index, failure_index)
        self.assertLess(busy_index, regression_index)
        self.assertLess(busy_index, quarantine_index)

    def test_busy_preflight_keeps_queue_mutation_out_of_busy_branch(self):
        text = SCRIPT.read_text()
        packet_index = text.index('c.commit(); p=packet(c,pid)')
        start = text.index(
            '        if gp.returncode==75:',
            packet_index,
        )
        end = text.index(
            '        if gp.returncode:',
            start + 1,
        )
        block = text[start:end]
        self.assertNotIn('update integration_queue', block)
        self.assertNotIn('regression-capture', block)
        self.assertNotIn('QUARANTINED', block)
        self.assertIn('return', block)
        self.assertNotIn('raise SystemExit(75)', block)


if __name__ == "__main__":
    unittest.main()
