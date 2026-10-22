"""file_format.py - Member B: header + payload reading/writing.

File layout (big-endian):
    magic            4 bytes   b"MHUF"
    version          1 byte
    original_length  4 bytes   number of original symbols (bytes)
    padding_bits     1 byte    0..7
    has_esc          1 byte    1 if an ESC symbol exists
    num_kept         2 bytes   number of kept symbols
    kept table       num_kept * (symbol 1 byte, frequency 4 bytes)
    esc frequency    4 bytes   only if has_esc == 1
    payload          packed bits
The frequencies let the decoder rebuild the same Huffman tree as the encoder.
"""
import os
import struct

from bit_writer import BitWriter, BitReader
from compression import ESC, huffman_frequencies

MAGIC = b"MHUF"
VERSION = 1
FIXED_HEADER = struct.Struct(">4sBIBBH")
ENTRY = struct.Struct(">BL")
ESC_ENTRY = struct.Struct(">I")
MAX_UNIT32 = 2 ** 32-1

def header_size(num_kept, has_esc):
    return FIXED_HEADER.size + ENTRY.size * num_kept + (ESC_ENTRY.size if has_esc else 0)


def build_huffman_frequencies(metadata):
    '''Kept symbol frequencies plus the combined ESC frequency.'''
    return huffman_frequencies(metadata["frequencies"], metadata["kept"], metadata["rare"])


def write_compressed_file(file_path, bit_string, metadata):
    '''Pack bit_string into bytes and save header + payload. Returns file size.'''
    if metadata["original_length"] > MAX_UNIT32:
        raise ValueError("input is too large forthis file format (max 4 GiB)")
    
    writer = BitWriter()
    writer.write_bits(bit_string)
    payload, padding_bits = writer.finish()

    huffman_frequencies = build_huffman_frequencies(metadata)
    kept_table = {s: f for s, f in huffman_frequencies.items() if s != ESC}
    has_esc = ESC in huffman_frequencies

    with open(file_path, "wb") as f:
        f.write(FIXED_HEADER.pack(MAGIC, VERSION, metadata["original_length"],
                                padding_bits, int(has_esc), len(kept_table)))
        for symbol in sorted(kept_table):
            f.write(ENTRY.pack(symbol, kept_table[symbol]))
        if has_esc:
            f.write(ESC_ENTRY.pack(huffman_frequencies[ESC]))
        f.write(payload)

    return os.path.getsize(file_path)


def read_compressed_file(file_path):
    '''Returns (header, BitReader). header has original_length and huffman_frequencies.'''
    with open(file_path, "rb") as f:
        data = f.read()

    if len(data) < FIXED_HEADER.size:
        raise ValueError("file is too small to be a compressed file.")

    magic, version, original_length, padding_bits, has_esc, num_kept = \
        FIXED_HEADER.unpack_from(data)

    if magic != MAGIC:
        raise ValueError("bad magic number: not a compressed file from this program.")
    if version != VERSION:
        raise ValueError(f"unsupported version {version}.")
    if has_esc not in (0,1):
        raise ValueError("corrupted file: bad ESC flag")
    if len(data) < header_size(num_kept, has_esc):
        raise ValueError("file is truncated inside the header.")

    position = FIXED_HEADER.size
    huffman_frequencies = {}
    previous = -1
    for _ in range(num_kept):
        symbol, frequency = ENTRY.unpack_from(data, position)
        if symbol <= previous :
            raise ValueError("corrupted file: symbol table is not strictly ascending.")
        if frequency == 0:
            raise ValueError("corrupted file : symbol with zero frequency")
        huffman_frequencies[symbol] = frequency
        previous = symbol
        position += ENTRY.size

    if has_esc:
        frequency = ESC_ENTRY.unpack_from(data,position)[0]
        if frequency ==0:
            raise ValueError("corrupted file: ESC with zero frequency")
        huffman_frequencies[ESC] = frequency
        position += ESC_ENTRY.size

    header = {
        "original_length": original_length,
        "padding_bits": padding_bits,
        "has_esc": bool(has_esc),
        "huffman_frequencies": huffman_frequencies,
    }
    return header, BitReader(data[position:], padding_bits)


def verify_file_size(file_path, expected_bits):
    '''Check: file size == header size + packed payload size.
    Returns (ok, file_size, header_bytes, payload_bytes).'''
    with open(file_path, "rb") as f:
        data = f.read()

    _, _, _, padding_bits, has_esc, num_kept = FIXED_HEADER.unpack_from(data)
    header_bytes = header_size(num_kept, has_esc)
    payload_bytes = len(data) - header_bytes

    expected_payload = (expected_bits + 7) // 8
    ok = (payload_bytes == expected_payload
          and padding_bits == payload_bytes * 8 - expected_bits)

    return ok, len(data), header_bytes, payload_bytes
