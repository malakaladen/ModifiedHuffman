from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import heapq
import math
from pathlib import Path

ESC = 256

@dataclass
class Node:
    symbol: int | None = None
    left: "Node | None" = None
    right: "Node | None" = None

def read_input_file(file_path):
    '''Read the input file and return its content as bytes.'''
    with open(file_path, "rb") as f:
        return f.read()   


def calculate_probabilities(data):
    freq = Counter(data)
    total = len(data)

    if total == 0:
        return freq, {}

    probabilities = {symbol: count / total for symbol, count in freq.items()}     
    return freq, probabilities



def split_symbols(probabilities, p_min):
    '''seperate kept symbols from rare symbols.'''
    if not 0 <= p_min <=1:
        raise ValueError("p_min must be between 0 and 1.")

    kept={symbol for symbol, probability in probabilities.items()  if probability > p_min}

    rare = set(probabilities) - kept
    return kept, rare

def build_huffman_tree(freq):
    if not freq:
        return None

    heap =[]
    serial=0
    for symbol in sorted(freq):
        node = Node(symbol=symbol)
        heapq.heappush(heap, (freq[symbol], symbol, serial, node))
        serial += 1

    while len(heap) >1:
        freq1,min1, _, left = heapq.heappop(heap)
        freq2,min2, _, right = heapq.heappop(heap)
        parent = Node(left=left, right=right)
        heapq.heappush( heap,(freq1 + freq2, min(min1,min2),serial,parent))
        serial +=1

    return heap[0][3]

def generate_codes(root):
    '''generate one prefix-free code for every leaf.'''
    codes = {}

    if root is None:
        return codes

    def visit(node,prefix):
        if node.symbol is not None:
            #A single-symbol tree still needs a 1-bit code.
            codes[node.symbol] = prefix or "0"
            return

        visit(node.left, prefix + "0")
        visit(node.right, prefix + "1")

    visit(root,"")
    return codes

def compress_data(data, p_min):
    '''
    Encode bytes using Modified Huffman.
     rare byte : ESC code + its original 8-bit representation .
     returns the bit string and metadata for the file-format member.'''
    freq, probabilities = calculate_probabilities(data)

    if not data:
        return"", {
            "frequencies": freq,
            "probabilities": probabilities,
            "kept": set(),
            "rare": set(),
            "codebook": {},
            "original_length": 0,
        }    
    kept, rare = split_symbols(probabilities, p_min)
    #Build the Huffman alphabet.
    huffman_frequencies = {symbol: freq[symbol] for symbol in kept}

    if rare:
        huffman_frequencies[ESC] = sum(freq[symbol] for symbol in rare)

    tree = build_huffman_tree(huffman_frequencies)
    codebook = generate_codes(tree)

    #Encode the input in its original order.
    output_bits = []

    for symbol in data:
        if symbol in kept:
            output_bits.append(codebook[symbol])
        else:
            output_bits.append(codebook[ESC])
            output_bits.append(f"{symbol:08b}")

    bit_string = "".join(output_bits)

    metadata = {
        "frequencies": freq,
        "probabilities": probabilities,
        "kept": kept,
        "rare": rare,
        "codebook": codebook,
        "original_length": len(data),
    }

    return bit_string, metadata

def calculate_statistics(data, metadata, bit_string):
    """Calculate entropy, average encodedlength and ratio."""
    total = len(data)
    if total == 0:
        return {
            "entropy": 0.0,
            "average_code_length": 0.0,
            "encoded_bits":0,
            "compression_ratio": None,
        }

    probabilities = metadata["probabilities"]
    codebook = metadata["codebook"]
    rare = metadata["rare"]

    entropy = -sum( p* math.log2(p)  for p in probabilities.values() if p > 0)

    esc_length = len(codebook[ESC]) if rare else 0
    #Include the 8 raw bits used for every rare symbol.
    average_length = sum(
        probabilities[symbol] * (esc_length + 8 
                        if symbol in rare
                        else len(codebook[symbol])
                    )
                    for symbol in probabilities
                )
    encoded_bits = len(bit_string)

    #payload-only ration: original bits / encoded payload bits.
    ratio = ((total *8) /encoded_bits if encoded_bits > 0  else None)

    return {
        "entropy": entropy,
        "average_code_length": average_length,
        "encoded_bits": encoded_bits,
        "compression_ratio":ratio,
    }                  

def main():
    input_path =Path("input.txt")
    p_min = float(input("Enter P_min (between 0 and 1): "))

    data = read_input_file(input_path)
    bit_string, metadata = compress_data(data, p_min)
    stats = calculate_statistics(data, metadata, bit_string)
    assert abs(stats["average_code_length"]* len(data) - len(bit_string)) < 1e-6

    print("\nSymbol probabilities:")
    for symbol, probability in sorted(metadata["probabilities"].items()):          
        print(f"Byte {symbol}: {probability:.6f}")

    print("\nKept symbols:", sorted(metadata["kept"]))
    print("Rare symbols:", sorted(metadata["rare"]))
    print("codebook:",metadata["codebook"])

    print("\nEncoded bit string:", bit_string)
    print("Entropy:", round(stats["entropy"], 4), "bits/symbol")
    print(
        "Average encoded length:",
        round(stats["average_code_length"], 4),
        "bits/symbol",
    )
    print("Encoded payload bits:", stats["encoded_bits"])
    print("Payload compression ratio:", stats["compression_ratio"])

    with open("encoded_preview.txt","w",encoding="ascii") as file:
        file.write(bit_string)

if __name__ == "__main__":
    main()
