"""Schema decoder tests use synthetic messages only."""
import struct
import unittest
from inspect_private_map_records import _field_bytes as blob, _field_varint as varint
from decode_private_map import decode_message, summarize_root


def fixed(n, v):
    return bytes([(n << 3) | 5]) + struct.pack('<f', v)


class SchemaTests(unittest.TestCase):
    def test_repeated_uvs_depth_order_and_large_update_date(self):
        position = fixed(1, -60) + fixed(2, 30)
        uv = fixed(1, 0.25) + fixed(2, 0.5)
        vertex = blob(1, position) + blob(2, uv) + blob(2, uv)
        chip = varint(1, 42) + varint(2, 3) + blob(5, vertex)
        grid = varint(1, 4) + varint(2, 5) + varint(3, 17) + blob(10, chip)
        tree = blob(2, blob(1, grid))
        root = decode_message(varint(2, 2**63 + 1) + varint(3, 120) + varint(4, 120) + blob(5, tree), 'Root')
        g = root['QuadTreeRoot']['QuadTrees'][0]['Grids'][0]
        self.assertEqual(root['UpdateDate'], 2**63 + 1)
        self.assertEqual(g['DepthOrder'], 17)
        self.assertEqual(g['Chips'][0]['Vertices'][0]['VertexPos']['PosX'], -60)
        self.assertEqual(len(g['Chips'][0]['Vertices'][0]['UvPoses']), 2)
        self.assertEqual(summarize_root(root)['grid_count'], 1)

    def test_rejects_schema_type_mismatch_and_nonfinite_geometry(self):
        with self.assertRaisesRegex(ValueError, 'wire type'):
            decode_message(blob(1, b'x'), 'Grid')
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            decode_message(fixed(1, float('nan')), 'VertexPos')

    def test_unknown_fields_are_counted_and_duplicate_singular_rejected(self):
        result = decode_message(varint(99, 5), 'Root')
        self.assertEqual(result['_unknown_fields'], ['99:0'])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            decode_message(varint(3, 120) + varint(3, 100), 'Root')


if __name__ == '__main__':
    unittest.main()
