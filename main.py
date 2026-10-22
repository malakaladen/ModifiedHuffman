"""main.py - command line + interactive menu for the Modified Huffman project.

Command line:
    python main.py compress   input.txt packed.bin  [--p-min 0.05]
    python main.py decompress packed.bin restored.txt
    python main.py analyze    input.txt             [--p-min 0.05]
    python main.py roundtrip  input.txt             [--p-min 0.05]
    python main.py sweep      input.txt
    python main.py test
    python main.py                       (no arguments -> interactive menu)

Everything printed is also appended to output_log.txt.
"""
import argparse
import os
import sys
import tempfile
import unittest
from datetime import datetime

from compression import (ESC , calculate_statistics, compress_data, read_input_file)
from decompression import decompress_file
from file_format import verify_file_size, write_compressed_file

DEFAULT_P_MIN = 0.05
TEST_P_VALUES = [0, 0.001, 0.01, 0.05, 0.2, 1.0]
SWEEP_P_VALUES = [0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]
MAX_BITS_SHOWN=200
LOG_PATH = "output_log.txt"


def out(*args, sep=" ", end="\n"):
    """Print to the screen AND append the same text to the log file."""
    text = sep.join(str(a) for a in args) + end
    sys.stdout.write(text)
    if _log:
        _log.write(text)
        _log.flush()


def log_only(text):
    """Save something (like what the user typed) to the log without printing it."""
    if _log:
        _log.write(text + "\n")
        _log.flush()


def start_log():
    global _log
    _log = open(LOG_PATH, "a", encoding="utf-8")
    _log.write(f"# Run started: {datetime.now():%Y-%m-%d %H:%M:%S}\n")

def stop_log():
    global _log
    if _log:
        _log.close()
        _log = None

# ======================================================================
# Shared helpers for compress / decompress
# ======================================================================
def compress_to(src, dst, p_min):
    """Compress file `src` into `dst`. Returns a dict with all the numbers."""
    data = read_input_file(src)
    bits, meta = compress_data(data, p_min)
    file_size = write_compressed_file(dst, bits, meta)
    ok, _, header_bytes, payload_bytes = verify_file_size(dst, len(bits))
    return {"data": data, "bits": bits, "meta": meta, "file_size": file_size,
            "size_ok": ok, "header_bytes": header_bytes, "payload_bytes": payload_bytes,
            "stats": calculate_statistics(data, meta, bits)}


def roundtrip_file(src, p_min, workdir):
    """Compress then decompress `src`; returns (identical?, info dict)."""
    packed = os.path.join(workdir, "packed.bin")
    restored = os.path.join(workdir, "restored.out")
    info = compress_to(src, packed, p_min)
    decompress_file(packed, restored)
    with open(restored, "rb") as f:
        info["identical"] = f.read() == info["data"]
    return info["identical"], info

def symbol_label(symbol):
    if symbol == ESC:
        return "ESC (rare)"
    return repr(chr(symbol)) if 32 <= symbol < 127 else f"byte {symbol}"

def run_tests():
    suite = unittest.defaultTestLoader.discover(os.path.dirname(os.path.abspath(__file__)),
                                                pattern="test_huffman.py")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
    return result.wasSuccessful()

# ======================================================================
# Menu actions
# ======================================================================

def ask_p_min():
    while True:
        text = input(f"Minimum symbol probability p_min (0..1) [{DEFAULT_P_MIN}]: ").strip()
        log_only(f"p_min: {text or DEFAULT_P_MIN}")
        try:
            p = float(text) if text else DEFAULT_P_MIN
        except ValueError:
            out("Please enter a number, e.g. 0.05")
            continue
        if 0 <= p <= 1:
            return p
        out("p_min must be between 0 and 1.")


def print_compression_report(info, dst, p_min):
    data, meta, stats = info["data"], info["meta"], info["stats"]
    out(f"\n  p_min               : {p_min}")
    out(f"  original size       : {len(data)} bytes")
    out(f"  compressed file     : {info['file_size']} bytes "
        f"(header {info['header_bytes']} + payload {info['payload_bytes']})")
    if info["file_size"]:
        out(f"  overall ratio       : {len(data) / info['file_size']:.3f}")
    out(f"  kept / rare symbols : {len(meta['kept'])} / {len(meta['rare'])}")
    out(f"  entropy             : {stats['entropy']:.4f} bits/symbol")
    out(f"  average code length : {stats['average_code_length']:.4f} bits/symbol")
    out(f"  payload bits        : {stats['encoded_bits']}")
    out(f"  size check          : {'OK' if info['size_ok'] else 'MISMATCH'}")
    codebook = meta["codebook"]
    if 0 < len(codebook) <= 40:
        out("  codebook:")
        for sym in sorted(codebook):
            label = "ESC (others)" if sym == ESC else (
                repr(chr(sym)) if 32 <= sym < 127 else f"byte {sym}")
            out(f"    {label:>14} -> {codebook[sym]}")
    out(f"  saved to            : {dst}")

def print_analysis(data, p_min):
    """Probabilities, kept/rare split, codebook, bit string and statistics."""
    bits, meta = compress_data(data, p_min)
    stats = calculate_statistics(data, meta, bits)

    out(f"\nInput: {len(data)} bytes, p_min = {p_min}")
    out("\nSymbol probabilities:")
    for symbol, p in sorted(meta["probabilities"].items()):
        status = "kept" if symbol in meta["kept"] else "rare"
        out(f"  {symbol_label(symbol):>12}  count={meta['frequencies'][symbol]:<8} "
            f"p={p:.6f}  {status}")

    out("\nCodebook:")
    for symbol in sorted(meta["codebook"]):
        out(f"  {symbol_label(symbol):>12} -> {meta['codebook'][symbol]}")

    shown = bits if len(bits) <= MAX_BITS_SHOWN else bits[:MAX_BITS_SHOWN] + "..."
    out(f"\nEncoded bit string ({len(bits)} bits): {shown}")
    out(f"Entropy              : {stats['entropy']:.4f} bits/symbol")
    out(f"Average code length  : {stats['average_code_length']:.4f} bits/symbol")
    ratio = stats["compression_ratio"]
    out(f"Payload ratio        : {ratio:.3f}" if ratio else "Payload ratio        : n/a")


def action_compress(src,dst,p_min):
    print_compression_report(compress_to(src,dst,p_min),dst,p_min)

def action_decompress(src,dst):
    out(f"\n restored {decompress_file(src, dst)} bytes -> {dst}")

def action_analyzer(src, p_min):
    print_analysis(read_input_file(src),p_min)

def action_roundtrip(src, p_min):
    with tempfile.TemporaryDirectory() as tmp:
        identical, info = roundtrip_file(src, p_min, tmp)
    print_compression_report(info, None, p_min)
    out("\n  ROUND TRIP:", "PASS - restored file is identical" if identical
        else "FAIL - restored file differs!")
    return identical


def action_sweep(src):
    data = read_input_file(src)
    out(f"\n  file: {src} ({len(data)} bytes)\n")
    out(f"  {'p_min':>7} {'rare':>5} {'avg len':>8} {'file size':>10} {'ratio':>7}  round trip")
    with tempfile.TemporaryDirectory() as tmp:
        for p in SWEEP_P_VALUES:
            identical, info = roundtrip_file(src, p, tmp)
            ratio = len(data) / info["file_size"] if info["file_size"] else 0
            out(f"  {p:>7} {len(info['meta']['rare']):>5} "
                f"{info['stats']['average_code_length']:>8.3f} "
                f"{info['file_size']:>10} {ratio:>7.3f}  {'OK' if identical else 'FAIL'}")

def ask(prompt,default=None):
    suffix=f"[{default}]" if default else ""
    while True:
        text = input(f"{prompt}{suffix}: ").strip().strip('"')
        log_only(f"{prompt}{suffix}: {text}")
        if text:
            return text
        if default:
            return default

        


MENU = [
    ("Compress a file",
        lambda: action_compress(ask("Input file"), ask("Compressed output file", "compressed.bin"),                    ask_p_min())),
    ("Decompress a file",
        lambda: action_decompress(ask("Compressed file"), ask("Restored output file", "restored.out"))),
    ("Analyze a file (probabilities, codebook, bit string, entropy)",
        lambda: action_analyzer(ask("Input file"), ask_p_min())),
    ("Round-trip test on a file (compress + decompress + compare)",
        lambda: action_roundtrip(ask("Input file"), ask_p_min())),
    ("p_min experiment on a file (size vs p_min table)",
        lambda: action_sweep(ask("Input file"))),
    ("Run ALL self-tests", run_tests),
]

def interactive():
    out(f"(Everything shown here is also saved to {os.path.abspath(LOG_PATH)})")
    try:
        while True:
            out("\n===Modified Huffman ===")
            for i, (label, _) in enumerate(MENU,1):
                out(f" {i}. {label}")
            out("  0.Exit")
            choice = input("Choose: ").strip()
            log_only(f"Choose: {choice}")
            if choice == "0":
                return
            if not choice.isdigit() or not 1 <= int(choice) <= len(MENU):
                out("plrase choose a number from the menu")
                continue
            try:
                MENU[int(choice)-1][1]()
            except (OSError,ValueError) as e:
                out(f"\n Error: {e}")
    except (EOFError, KeyboardInterrupt):
        out("\nBye")                

def p_min_value(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
    if not 0 <= value <=1:
        raise argparse.ArgumentTypeError("p_min must be between a and 1")
    return value

def build_parser():
    parser = argparse.ArgumentTypeError(descreption="Modified Huffman compression.")
    sub = parser.add_subparsers(dest="command")

    def add(name, help_text, *positionals, p_min=False):
        p= sub.add_parser(name, help=help_text)
        for arg in positionals:
            p.add_argument(arg)
            if p_min:
                p.add_argument("--p-min", type=p_min_value, default = DEFAULT_P_MIN, help=f"rarity threshold in [0,1] (default {DEFAULT_P_MIN})")

    add("compress", "compress a file", "input", "output", p_min=True)
    add("decompress", "restore a compressed file", "input", "output")
    add("analyze", "show probabilities, codebook, bit string, statistics", "input", p_min=True)
    add("roundtrip", "compress + decompress + compare", "input", p_min=True)
    add("sweep", "table of results for many p_min values", "input")
    add("test", "run all self-tests")
    return parser



def main(argv=None):
    args = build_parser().parse_args(argv)
    start_log()
    try:
        if args.command is None:
            interactive()
            return 0
        try:
            if args.command == "compress":
                action_compress(args.input, args.output, args.p_min)
            elif args.command == "decompress":
                action_decompress(args.input, args.output)
            elif args.command == "analyze":
                action_analyzer(args.input, args.p_min)
            elif args.command == "roundtrip":
                return 0 if action_roundtrip(args.input, args.p_min) else 1
            elif args.command == "sweep":
                action_sweep(args.input)
            elif args.command == "test":
                return 0 if run_tests() else 1
        except (OSError, ValueError) as e:
            out(f"Error: {e}")
            return 1
        return 0
    finally:
        stop_log()


if __name__ == "__main__":
    sys.exit(main())
