"""Synthetic source inventory tests. No recovered client data."""
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from hydrate_private_assets import _make_synthetic_mbn
from inspect_private_sources import inspect_sources, json_evidence


class SourceInventoryTests(unittest.TestCase):
    def test_mbn_json_evidence_excludes_dialog_and_binary_payloads(self):
        with tempfile.TemporaryDirectory() as raw:
            archive = Path(raw) / 'private.zip'
            config = {'tutorial': {'map_id': '001_000_00700', 'spawn': [12, 34]},
                      'initial_view_scale': 1.25, 'dialog': 'PRIVATE DIALOG MUST NOT EXPORT'}
            with ZipFile(archive, 'w') as z:
                z.writestr('files/cache/patch/settings.mbn',
                           _make_synthetic_mbn('field_settings.json', json.dumps(config).encode()))
                z.writestr('files/cache/patch/image.mbn', _make_synthetic_mbn('pic.astc', b'PRIVATE IMAGE'))
            result = inspect_sources(archive)
            encoded = json.dumps(result)
            self.assertNotIn('PRIVATE DIALOG MUST NOT EXPORT', encoded)
            self.assertNotIn('PRIVATE IMAGE', encoded)
            self.assertIn('001_000_00700', encoded)
            self.assertIn('/tutorial/map_id', encoded)
            self.assertEqual(result['mbn_entry_suffix_counts']['.astc'], 1)
            self.assertEqual(result['sources'][0]['json_evidence']['settings'][0]['value'], 1.25)

    def test_map_references_are_exact_and_provenance_kept(self):
        evidence = json_evidence({'a/b': ['001_000_00002'], 'text': 'visit 001_000_00700 now'})
        self.assertEqual(evidence['resource_id_candidates'], [{'pointer': '/a~1b/0', 'resource_id': '001_000_00002'}])
        evidence = json_evidence({'sound_id': '100_002_00065'})
        self.assertNotIn('map_references', evidence)


if __name__ == '__main__':
    unittest.main()
