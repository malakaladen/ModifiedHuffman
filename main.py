"""main.py - simple menu: compress or decompress a file.

  python main.py

Needs in the same folder: compression.py, file_format.py, bit_writer.py, decompression.py
"""
import os

from compression import ESC, read_input_file, compress_data, calculate_statistics
from file_format import write_compressed_file, verify_file_size
from decompression import decompress_file

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_P_MIN = 0.05


def ask(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    while True:
        text = input(f"{prompt}{suffix}: ").strip().strip('"')
        if text:
            return text
        if default:
            return default


def ask_input_file():
    """Ask for a file; relative names are also looked up next to main.py."""
    path = ask("Input file", "input.txt")
    if not os.path.isabs(path) and not os.path.exists(path):
        path = os.path.join(HERE, path)
    return os.path.abspath(path)


def ask_output_file(prompt, default_name):
    """Relative names are saved next to main.py so the output is easy to find."""
    path = ask(prompt, default_name)
    return path if os.path.isabs(path) else os.path.join(HERE, path)


def ask_p_min():
    while True:
        text = input(f"p_min, minimum symbol probability (0..1) [{DEFAULT_P_MIN}]: ").strip()
        try:
            p = float(text) if text else DEFAULT_P_MIN
        except ValueError:
            print("Please enter a number, e.g. 0.05")
            continue
        if 0 <= p <= 1:
            return p
        print("p_min must be between 0 and 1.")


def action_compress():
    src = ask_input_file()
    dst = ask_output_file("Compressed output file", "compressed.bin")
    p_min = ask_p_min()

    data = read_input_file(src)
    bits, meta = compress_data(data, p_min)
    file_size = write_compressed_file(dst, bits, meta)
    ok, _, header_bytes, payload_bytes = verify_file_size(dst, len(bits))
    stats = calculate_statistics(data, meta, bits)

    if not data:
        print("\n  WARNING: the input file is empty (0 bytes). Is it saved?")
    print(f"\n  p_min               : {p_min}")
    print(f"  original size       : {len(data)} bytes")
    print(f"  compressed file     : {file_size} bytes "
          f"(header {header_bytes} + payload {payload_bytes})")
    if file_size:
        print(f"  overall ratio       : {len(data) / file_size:.3f}")
    print(f"  kept / rare symbols : {len(meta['kept'])} / {len(meta['rare'])}")
    print(f"  entropy             : {stats['entropy']:.4f} bits/symbol")
    print(f"  average code length : {stats['average_code_length']:.4f} bits/symbol")
    print(f"  payload bits        : {stats['encoded_bits']}")
    print(f"  size check          : {'OK' if ok else 'MISMATCH'}")
    codebook = meta["codebook"]
    if 0 < len(codebook) <= 40:
        print("  codebook:")
        for sym in sorted(codebook):
            label = "ESC (others)" if sym == ESC else (
                repr(chr(sym)) if 32 <= sym < 127 else f"byte {sym}")
            print(f"    {label:>14} -> {codebook[sym]}")
    print(f"  saved to            : {dst}")


def action_decompress():
    src = ask_output_file("Compressed file", "compressed.bin")
    dst = ask_output_file("Restored output file", "restored.txt")
    n = decompress_file(src, dst)
    print(f"\n  restored {n} bytes -> {dst}")


MENU = [("Compress a file", action_compress),
        ("Decompress a file", action_decompress)]


def main():
    try:
        while True:
            print("\n=== Modified Huffman ===")
            for i, (label, _) in enumerate(MENU, 1):
                print(f"  {i}. {label}")
            print("  0. Exit")
            choice = input("Choose: ").strip()
            if choice == "0":
                break
            if not choice.isdigit() or not 1 <= int(choice) <= len(MENU):
                print("Please choose a number from the menu.")
                continue
            try:
                MENU[int(choice) - 1][1]()
            except (OSError, ValueError, EOFError) as e:
                print(f"\n  Error: {e}")
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")


if __name__ == "__main__":
    main()
