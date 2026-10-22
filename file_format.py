import json
import os
import struct

from bitwriter import BitWriter, BitReader


ESC = 256
MAGIC = b"MHF1"


def write_compressed_file(output_path, bit_string, metadata):
    '''
    Pack the encoded bits and save the header and payload.
    Return file-size information.
    '''
    writer = BitWriter()
    writer.write_bits(bit_string)

    payload, padding_bits = writer.finish()
    codebook = metadata["codebook"]
    symbol_table = []

    for symbol, code in sorted(codebook.items()):
        if symbol == ESC:
            frequency = sum(
                metadata["frequencies"][s]
                for s in metadata["rare"]
            )
        else:
            frequency = metadata["frequencies"][symbol]

        symbol_table.append({
            "symbol": symbol,
            "frequency": frequency,
            "code": code,
            "code_length": len(code),
        })

    header = {
        "version": 1,
        "original_length": metadata["original_length"],
        "bit_count": writer.bit_count,
        "padding_bits": padding_bits,
        "has_esc": ESC in codebook,
        "symbol_table": symbol_table,
    }

    header_bytes = json.dumps(
        header, separators=(",", ":")
    ).encode("utf-8")

    #Store the header length before the header itself.
    with open(output_path, "wb") as file:
        file.write(MAGIC)
        file.write(struct.pack(">I", len(header_bytes)))
        file.write(header_bytes)
        file.write(payload)

    header_size = 8 + len(header_bytes)
    expected_size = header_size + (writer.bit_count + 7) // 8
    actual_size = os.path.getsize(output_path)

    if actual_size != expected_size:
        raise OSError("file size does not match expected size.")

    return {
        "output_path": str(output_path),
        "header_bytes": header_size,
        "payload_bytes": len(payload),
        "padding_bits": padding_bits,
        "file_bytes": actual_size,
    }


def read_compressed_file(input_path):
    '''
    Read the header and packed bytes.
    Return the header, codebook and BitReader.
    '''
    with open(input_path, "rb") as file:
        if file.read(4) != MAGIC:
            raise ValueError("invalid compressed file.")

        size_bytes = file.read(4)

        if len(size_bytes) != 4:
            raise ValueError("missing header length.")

        header_size = struct.unpack(">I", size_bytes)[0]
        header_bytes = file.read(header_size)

        if len(header_bytes) != header_size:
            raise ValueError("incomplete header.")

        header = json.loads(header_bytes.decode("utf-8"))
        payload = file.read()

    if header["version"] != 1:
        raise ValueError("unsupported file version.")

    original_length = header["original_length"]
    bit_count = header["bit_count"]

    if type(original_length) is not int or original_length < 0:
        raise ValueError("invalid original length.")

    if type(bit_count) is not int or bit_count < 0:
        raise ValueError("invalid bit count.")

    codebook = {}
    total_frequency = 0

    for entry in header["symbol_table"]:
        symbol = entry["symbol"]
        code = entry["code"]
        frequency = entry["frequency"]

        if type(symbol) is not int or not 0 <= symbol <= ESC:
            raise ValueError("invalid symbol.")

        if symbol in codebook:
            raise ValueError("duplicate symbol.")

        if not isinstance(code, str) or not code:
            raise ValueError("invalid code.")

        if any(bit not in "01" for bit in code):
            raise ValueError("codes must contain only 0 and 1.")

        if entry["code_length"] != len(code):
            raise ValueError("incorrect code length.")

        if type(frequency) is not int or frequency <= 0:
            raise ValueError("invalid frequency.")

        codebook[symbol] = code
        total_frequency += frequency

    if total_frequency != original_length:
        raise ValueError("frequencies do not match original length.")

    if header["has_esc"] != (ESC in codebook):
        raise ValueError("incorrect ESC information.")

    codes = sorted(codebook.values())

    for first, second in zip(codes, codes[1:]):
        if second.startswith(first):
            raise ValueError("codebook must be prefix-free.")

    reader = BitReader(payload, header["padding_bits"])

    if reader.total_bits != bit_count:
        raise ValueError("incorrect payload size or padding.")

    if original_length == 0:
        if bit_count or codebook:
            raise ValueError("invalid empty-file metadata.")
    elif not bit_count or not codebook:
        raise ValueError("missing codes or encoded bits.")

    return header, codebook, reader
