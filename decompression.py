from compression import ESC, build_huffman_tree
from file_format import read_compressed_file


def decode_data(header, reader):
    """Rebuild the Huffman tree from the header frequencies and decode the bits."""
    original_length = header["original_length"]
    frequencies = header["huffman_frequencies"]

    if original_length == 0:
        if frequencies or reader.total_bits:
            raise ValueError("corrupted file: data present in an empty file.")
        return b""


    if not frequencies:
        raise ValueError("corrupted file: empty symbol table.")
    if sum(frequencies.values()) != original_length:
        raise ValueError("corrupted file: frequencies do not match the original length.")

    # Same function and same tie-breaking as the encoder -> same tree.
    root = build_huffman_tree(frequencies)
    bits = reader.bit_string()
    end = len(bits)
    pos=0
    output = bytearray()

    while len(output) < original_length:
        if root.symbol is not None:
            # Only one symbol exists: its code is the single bit "0".
            if pos >=end:
                raise EOFError
            pos +=1
            symbol = root.symbol
        else:
            node = root
            while node.symbol is None:
                if pos >= end:
                    raise EOFError
                node = node.right if bits[pos] == "1" else node.left
                pos +=1
            symbol = node.symbol

        if symbol == ESC:
            if pos +8 >end:
                raise EOFError
            output.append(int(bits[pos:pos +8],2))
            pos +=8
        else:
            output.append(symbol)

    if pos !=end:
        raise ValueError("corrupted file: Extra bits after the last symbol")
    if not reader.padding_is_zero():
        raise ValueError("corrupted file:padding bits are not zero.")

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
