"""Synthetic evidence tests, containing no recovered client bytes."""
import json
import struct
import unittest
from inspect_private_map_records import _field_bytes as blob, _field_varint as varint
from inspect_private_map_nested import profile_records, scan_blob


def fixed(number, value):
    return bytes([(number << 3) | 5]) + struct.pack('<f', value)


class NestedEvidenceTests(unittest.TestCase):
    def test_nested_paths_and_atlas_residuals(self):
        pair = fixed(1, 0.125) + fixed(2, 0.25)
        vertex = blob(1, fixed(1, -30) + fixed(2, 60)) + blob(2, pair)
        part = varint(1, 7) + varint(2, 0) + blob(5, vertex)
        records = [varint(1, 3) + varint(2, 4) + varint(3, 0) + blob(10, part)]
        result = profile_records(records, {'CHIP': [8, 12], 'OBJ': [10, 10]}, [120, 120])
        field = result['paths']['record/10/5/2']['fields']['1:5']['f32']
        self.assertEqual(field['count'], 1)
        self.assertEqual(field['min'], 0.125)
        self.assertEqual(field['scaled_integer_hits']['CHIP.width'], 1)
        self.assertEqual(field['scaled_integer_hits']['OBJ.width'], 0)
        self.assertEqual(result['record_relations']['unique_field1_field2_pairs'], 1)
        self.assertEqual(result['record_relations']['field3_unique_count'], 1)
        self.assertEqual(result['record_relations']['within_root_3_4'], 1)
        self.assertEqual(result['paths']['record/10']['multiplicities']['5:2'], {'1': 1})
        self.assertNotIn('hex', json.dumps(result))

    def test_opaque_and_nonfinite_are_not_silently_dropped(self):
        result = profile_records([blob(10, b'\xff') + fixed(4, float('nan'))], {}, [])
        self.assertEqual(result['opaque_length_fields'], {'record/10': 1})
        stats = result['paths']['record']['fields']['4:5']['f32']
        self.assertEqual(stats['nonfinite_count'], 1)
        json.dumps(result, allow_nan=False)

    def test_scan_reports_only_offsets_for_allowlisted_terms(self):
        result = scan_blob(b'private secret tutorial field_settings initial_view_scale 001_000_00002')
        self.assertEqual(result['tutorial']['count'], 1)
        self.assertNotIn('private secret', json.dumps(result))
        self.assertIn('001_000_00002', result)


if __name__ == '__main__':
    unittest.main()
