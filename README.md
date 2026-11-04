# Modified Huffman Compression

A Python implementation of a modified Huffman coding algorithm that compresses files into a binary format and restores them through decompression.

## ✨ How It Works

The compressor calculates each byte's probability and compares it with a configurable minimum threshold (`p_min`):

- **Frequent symbols** are kept as individual Huffman symbols.
- **Rare symbols** are grouped under a special ESC symbol.
- Each rare symbol is then represented by the ESC code followed by its original 8-bit value.
- The resulting bit stream is packed into bytes and stored with a header containing the information needed for decoding.

The decoder reads the header, rebuilds the Huffman tree, and reconstructs the original file.

## 🚀 Features

- File compression and decompression
- Configurable minimum symbol probability (`p_min`)
- ESC handling for low-probability symbols
- Binary output with packed bits
- Header metadata for rebuilding the Huffman tree
- Validation for invalid or corrupted compressed files

## 🛠️ Built With

- Python
- Huffman coding
- Binary file I/O
- Bit-level packing and reading

## 📂 Project Files

| File | Responsibility |
|---|---|
| `main.py` | Interactive menu for compression and decompression |
| `compression.py` | Probability calculation, symbol grouping, Huffman tree, and encoding |
| `decompression.py` | Huffman tree reconstruction and decoding |
| `file_format.py` | Binary header and compressed-file reading/writing |
| `bit_writer.py` | Packing bits into bytes and reading them back |

## ▶️ Run the Project

**Requirement:** Python 3.10 or later.

1. Clone the repository:

   ```bash
   git clone https://github.com/malakaladen/ModifiedHuffman.git
   cd ModifiedHuffman
   ```

2. Make sure the Python files listed above are in the same folder.
3. Run:

   ```bash
   python main.py
   ```

4. Choose **Compress a file** or **Decompress a file** from the menu.
5. For compression, enter the input file path, output file name, and `p_min` value. Press Enter to use the default threshold (`0.05`).

## 📦 Compressed File Format

The output file uses the `MHUF` magic signature and stores:

- Format version
- Original file length
- Number of padding bits
- ESC flag
- Frequencies for retained symbols and, when needed, the combined ESC symbol
- Packed compressed payload

All header fields are written in big-endian order.

## 🧪 Example

If the input file is `input.txt`, select the compression option and use `compressed.bin` as the output. Then select decompression and use `compressed.bin` as the input and `restored.txt` as the output.

The restored file should contain the original bytes.

---

<p align="center">
  Developed as a university Data Compression project.
</p>
