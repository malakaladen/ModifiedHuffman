from compression import build_huffman_tree
from file_format import read_compressed_file, ESC


def _read_bit(reader):
    bit = reader.read_bit()
    if bit is None:                      # tolerate a BitReader that returns None at the end
        raise EOFError("no more valid bits.")
    return bit


def _read_byte(reader):
    value = reader.read_bits(8)
    return int(value, 2) if isinstance(value, str) else value   # int or "01010101"


def decode_data(header, reader):
    """Rebuild the Huffman tree from the header frequencies and decode the bits."""
    original_length = header["original_length"]
    frequencies = header["huffman_frequencies"]
    output = bytearray()

    if original_length == 0:
        return bytes(output)

    if not frequencies:
        raise ValueError("corrupted file: empty symbol table.")
    if sum(frequencies.values()) != original_length:
        raise ValueError("corrupted file: frequencies do not match the original length.")

    # Same function and same tie-breaking as the encoder -> same tree.
    root = build_huffman_tree(frequencies)

    while len(output) < original_length:
        if root.symbol is not None:
            # Only one symbol exists: its code is the single bit "0".
            _read_bit(reader)
            symbol = root.symbol
        else:
            node = root
            while node.symbol is None:
                node = node.right if _read_bit(reader) else node.left
            symbol = node.symbol

        if symbol == ESC:
            output.append(_read_byte(reader))   # rare symbol: next 8 bits are the raw byte
        else:
            output.append(symbol)

    if reader.position != reader.total_bits:
        raise ValueError("corrupted file: extra bits after the last symbol.")

    return bytes(output)


def decompress_file(input_path, output_path):
    """Read a compressed file and write the restored file. Returns bytes restored."""
    header, reader = read_compressed_file(input_path)
    try:
        data = decode_data(header, reader)
    except EOFError:
        raise ValueError("corrupted file: compressed data ended too early.")

    with open(output_path, "wb") as f:      # written only after decoding succeeded
        f.write(data)
    return len(data)
