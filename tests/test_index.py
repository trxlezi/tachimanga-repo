import unittest
from build_index import fields, varint, string


def encode_varint(value):
    output = bytearray()
    while value >= 128:
        output.append((value & 127) | 128)
        value >>= 7
    output.append(value)
    return bytes(output)


class ProtobufIdentityTests(unittest.TestCase):
    def test_large_source_id_keeps_all_bits(self):
        source_id = 6003330990591348231
        parsed = fields(b'\x08' + encode_varint(source_id))
        self.assertEqual(str(parsed[1][0]), '6003330990591348231')

    def test_nested_extension_list_field_101(self):
        payload = b'\x0a\x03abc'
        parsed = fields(encode_varint((101 << 3) | 2) + encode_varint(len(payload)) + payload)
        self.assertEqual(string(fields(parsed[101][0]), 1), 'abc')

    def test_repeated_sources_are_not_overwritten(self):
        self.assertEqual(fields(b'\x42\x01a\x42\x01b')[8], [b'a', b'b'])

    def test_truncated_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            fields(b'\x0a\x09short')


if __name__ == '__main__':
    unittest.main()
