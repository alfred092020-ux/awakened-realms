import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DoctorSourceTests(unittest.TestCase):
    def test_re_evidence_integrity_uses_immutable_read_only_sqlite(self):
        source = (ROOT / 'bin' / 'logres-doctor').read_text()
        self.assertIn('(\"re_evidence_db\",Path(\"/home/ubuntu/logres/index/re-evidence.sqlite\"),True)', source)
        self.assertIn('?mode=ro&immutable=1', source)
        self.assertIn('sqlite3.connect(uri, uri=True)', source)

    def test_live_databases_do_not_use_immutable_mode(self):
        source = (ROOT / 'bin' / 'logres-doctor').read_text()
        self.assertIn('(\"control_db\",Path(\"/home/ubuntu/logres/control/control.sqlite\"),False)', source)
        self.assertIn('(\"ai_db\",Path(\"/home/ubuntu/logres/control/ai.sqlite\"),False)', source)

if __name__ == '__main__':
    unittest.main()
