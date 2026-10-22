"""test_huffman.py - tests for every module.   Run:  python -m unittest -v
"""
import os
import random
import struct
import tempfile
import unittest

from bit_writer import BitWriter, BitReader
from compression import (ESC, calculate_probabilities, calculate_statistics,
                         compress_data, read_input_file, split_symbols)
from decompression import decompress_file
from file_format import (FIXED_HEADER, build_huffman_frequencies,
                         read_compressed_file, verify_file_size,
                         write_compressed_file)

P_VALUES = [0, 0.001, 0.01, 0.05, 0.2, 1.0]
SAMPLE = b"a" * 60 + b"b" * 30 + b"c" * 7 + b"d" * 3


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def path(self, name):
        return os.path.join(self.tmp, name)

    def write(self, name, content):
        with open(self.path(name), "wb") as f:
            f.write(content)
        return self.path(name)

    def roundtrip(self, data, p_min):
        src = self.write("src", data)
        packed, restored = self.path("packed.bin"), self.path("restored.out")
        bits, meta = compress_data(read_input_file(src), p_min)
        size = write_compressed_file(packed, bits, meta)
        self.assertEqual(verify_file_size(packed, len(bits))[:2], (True, size))
        decompress_file(packed, restored)
        with open(restored, "rb") as f:
            self.assertEqual(f.read(), data)


class BitIOTests(unittest.TestCase):
    def test_write_read_various_lengths(self):
        rng = random.Random(1)
        for n in (0, 1, 7, 8, 9, 1000):
            with self.subTest(bits=n):
                bits = [rng.randint(0, 1) for _ in range(n)]
                w = BitWriter()
                w.write_bits("".join(map(str, bits)))
                payload, pad = w.finish()
                self.assertEqual(pad, (8 - n % 8) % 8)
                self.assertEqual(len(payload), (n + 7) // 8)
                r = BitReader(payload, pad)
                self.assertEqual([r.read_bit() for _ in range(n)], bits)
                self.assertEqual(r.total_bits, n)
                self.assertEqual(r.bit_string(), "".join(map(str, bits)))

    def test_bulk_write_matches_bit_by_bit(self):
        rng = random.Random(2)
        for offset in range(8):            # start with every possible partial byte
            text = "".join(rng.choice("01") for _ in range(203))
            slow, fast = BitWriter(), BitWriter()
            for b in text[:offset]:
                slow.write_bit(b)
                fast.write_bit(b)
            for b in text[offset:]:
                slow.write_bit(b)
            fast.write_bits(text[offset:])
            self.assertEqual(slow.finish(), fast.finish())
            self.assertEqual(slow.total_bits, fast.total_bits)

    def test_padding_is_zero_filled(self):
        w = BitWriter()
        w.write_bits("101")
        self.assertEqual(w.finish(), (bytes([0b10100000]), 5))

    def test_read_bits_returns_integer(self):
        w = BitWriter()
        w.write_bits("10100101" + "110")
        r = BitReader(*w.finish())
        self.assertEqual(r.read_bits(8), 0xA5)
        self.assertEqual(r.read_bits(3), 0b110)

    def test_reader_stops_at_end(self):
        w = BitWriter()
        w.write_bits("101")
        r = BitReader(*w.finish())
        for _ in range(3):
            r.read_bit()
        with self.assertRaises(EOFError):
            r.read_bit()

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            BitWriter().write_bit(2)
        with self.assertRaises(ValueError):
            BitWriter().write_bits("0102")
        with self.assertRaises(ValueError):
            BitReader(b"\x00", 8)


class CompressionTests(unittest.TestCase):
    def test_probabilities_sum_to_one(self):
        freq, p = calculate_probabilities(SAMPLE)
        self.assertAlmostEqual(sum(p.values()), 1)
        self.assertEqual(freq[ord("a")], 60)

    def test_split_by_p_min(self):
        _, p = calculate_probabilities(SAMPLE)
        self.assertEqual(split_symbols(p, 0.05), ({97, 98, 99}, {100}))

    def test_p_min_out_of_range_rejected(self):
        _, p = calculate_probabilities(SAMPLE)
        for bad in (-0.1, 1.5):
            with self.assertRaises(ValueError):
                split_symbols(p, bad)

    def test_esc_frequency_is_sum_of_rare(self):
        _, meta = compress_data(SAMPLE, 0.05)
        table = build_huffman_frequencies(meta)
        self.assertEqual(table[ESC], 3)
        self.assertEqual(sum(table.values()), len(SAMPLE))

    def test_codes_are_prefix_free_and_complete(self):
        _, meta = compress_data(SAMPLE, 0.05)
        codes = list(meta["codebook"].values())
        for i, x in enumerate(codes):
            for j, y in enumerate(codes):
                self.assertTrue(i == j or not y.startswith(x), f"{x} prefixes {y}")
        self.assertAlmostEqual(sum(2 ** -len(c) for c in codes), 1)

    def test_bit_count(self):
        bits, meta = compress_data(SAMPLE, 0.05)
        cb = meta["codebook"]
        expected = sum(len(cb[s]) if s in meta["kept"] else len(cb[ESC]) + 8
                       for s in SAMPLE)
        self.assertEqual(len(bits), expected)

    def test_single_symbol(self):
        bits, meta = compress_data(b"A" * 10, 0.05)
        self.assertEqual(meta["codebook"], {65: "0"})
        self.assertEqual(bits, "0" * 10)

    def test_empty_input(self):
        bits, meta = compress_data(b"", 0.05)
        self.assertEqual((bits, meta["codebook"]), ("", {}))
        self.assertEqual(calculate_statistics(b"", meta, bits)["encoded_bits"], 0)

    def test_p_min_zero_is_plain_huffman(self):
        _, meta = compress_data(SAMPLE, 0)
        self.assertFalse(meta["rare"])
        self.assertNotIn(ESC, meta["codebook"])

    def test_all_symbols_rare(self):
        _, meta = compress_data(b"abcabc", 1.0)
        self.assertFalse(meta["kept"])
        self.assertEqual(meta["rare"], {97, 98, 99})
        self.assertEqual(meta["codebook"], {ESC: "0"})

    def test_statistics(self):
        data = b"ab" * 50
        bits, meta = compress_data(data, 0)
        s = calculate_statistics(data, meta, bits)
        self.assertAlmostEqual(s["entropy"], 1.0)
        self.assertAlmostEqual(s["average_code_length"], 1.0)
        self.assertEqual(s["encoded_bits"], len(bits))
        self.assertAlmostEqual(s["compression_ratio"], 8.0)

    def test_average_length_matches_real_output(self):
        for p in P_VALUES:
            bits, meta = compress_data(SAMPLE, p)
            s = calculate_statistics(SAMPLE, meta, bits)
            self.assertAlmostEqual(s["average_code_length"] * len(SAMPLE), len(bits))


class FileFormatTests(TempDirCase):
    def setUp(self):
        super().setUp()
        self.data = b"the quick brown fox jumps over the lazy dog. " * 40
        self.bits, self.meta = compress_data(self.data, 0.05)
        self.packed = self.path("ff.bin")
        self.size = write_compressed_file(self.packed, self.bits, self.meta)
        with open(self.packed, "rb") as f:
            self.raw = f.read()

    def test_header_round_trip(self):
        header, reader = read_compressed_file(self.packed)
        self.assertEqual(header["original_length"], len(self.data))
        self.assertEqual(header["huffman_frequencies"], build_huffman_frequencies(self.meta))
        self.assertEqual(reader.total_bits, len(self.bits))

    def test_file_size_is_header_plus_payload(self):
        ok, fsize, _, pbytes = verify_file_size(self.packed, len(self.bits))
        self.assertTrue(ok)
        self.assertEqual(fsize, self.size)
        self.assertEqual(pbytes, (len(self.bits) + 7) // 8)

    def test_payload_is_real_bits_not_text(self):
        *_, pbytes = verify_file_size(self.packed, len(self.bits))
        self.assertLess(pbytes * 8, len(self.bits) + 8)

    def test_bad_files_are_rejected(self):
        symbol_table_start = FIXED_HEADER.size
        swapped = bytearray(self.raw)           # make symbols non-ascending
        swapped[symbol_table_start] = 0xFF
        zero_freq = bytearray(self.raw)         # first frequency -> 0
        zero_freq[symbol_table_start + 1:symbol_table_start + 5] = b"\0\0\0\0"
        bad_flag = bytearray(self.raw)
        bad_flag[10] = 7
        cases = {"wrong magic": b"XXXX" + self.raw[4:],
                 "too small": b"MH",
                 "cut inside header": self.raw[:12],
                 "unsorted symbol table": bytes(swapped),
                 "zero frequency": bytes(zero_freq),
                 "bad ESC flag": bytes(bad_flag)}
        for name, content in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    read_compressed_file(self.write("bad.bin", content))


class RoundTripTests(TempDirCase):
    def test_round_trips(self):
        rng = random.Random(3)
        cases = {
            "empty file": b"",
            "one repeated character": b"A" * 100,
            "two symbols": b"AB" * 50,
            "normal text": b"the quick brown fox jumps over the lazy dog. " * 60,
            "text with rare symbols": b"a" * 600 + b"b" * 300 + b"c" * 70 + bytes(range(100, 130)),
            "skewed binary": bytes(rng.choices(range(256), [60] + [1] * 255, k=5000)),
            "uniform random": bytes(rng.getrandbits(8) for _ in range(3000)),
            "all 256 byte values": bytes(range(256)) * 5,
            "newlines and UTF-8": "héllo wörld\r\n\r\nمرحبا\n".encode("utf-8") * 30,
        }
        for name, data in cases.items():
            for p in P_VALUES:
                with self.subTest(case=name, p_min=p):
                    self.roundtrip(data, p)

    def test_larger_file(self):
        rng = random.Random(4)
        self.roundtrip(bytes(rng.choices(range(256), [50] + [1] * 255, k=300_000)), 0.01)

    def test_skewed_data_really_compresses(self):
        data = b"a" * 9000 + b"b" * 900 + b"c" * 100
        bits, _ = compress_data(data, 0.05)
        self.assertLess(len(bits), len(data) * 8 // 4)


class DamagedFileTests(TempDirCase):
    def setUp(self):
        super().setUp()
        self.data = b"the quick brown fox jumps over the lazy dog. " * 60
        bits, meta = compress_data(self.data, 0.05)
        self.packed = self.path("dmg.bin")
        self.out = self.path("dmg.out")
        write_compressed_file(self.packed, bits, meta)
        with open(self.packed, "rb") as f:
            self.raw = f.read()

    def assert_clean_error(self, content):
        self.write("dmg.bin", content)
        with self.assertRaises(ValueError):
            decompress_file(self.packed, self.out)
        self.assertFalse(os.path.exists(self.out), "a partial output file was left behind")

    def test_payload_cut_short(self):
        self.assert_clean_error(self.raw[:-5])

    def test_frequency_table_damaged(self):
        flipped = bytearray(self.raw)
        flipped[16] ^= 0x40
        self.assert_clean_error(bytes(flipped))

    def test_not_a_compressed_file(self):
        self.assert_clean_error(b"hello world, definitely not compressed")

    def test_extra_bytes_appended(self):
        self.assert_clean_error(self.raw + b"\xff\xff")

    def test_nonzero_padding_bits(self):
        data = b"abaacaadaa"                       # payload is not a multiple of 8 bits
        bits, meta = compress_data(data, 0.15)
        write_compressed_file(self.packed, bits, meta)
        with open(self.packed, "rb") as f:
            raw = bytearray(f.read())
        self.assertGreater(raw[9], 0, "test data should need padding bits")
        decompress_file(self.packed, self.out)    # untouched file is fine
        os.remove(self.out)
        raw[-1] |= 1                              # set the last (padding) bit
        self.assert_clean_error(bytes(raw))

    def test_too_large_original_length_rejected_cleanly(self):
        tampered = bytearray(self.raw)
        tampered[5:9] = struct.pack(">I", 2 ** 32 - 1)
        self.assert_clean_error(bytes(tampered))


if __name__ == "__main__":
    unittest.main(verbosity=2)
