from collections import Counter
from dataclasses import dataclass
import heapq
import math

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

    stack = [(root, "")]
    while stack:
        node, prefix =stack.pop()
        if node.symbol is not None:
            codes[node.symbol] = prefix or "0"
        else:
            stack.append((node.left, prefix + "0"))
            stack.append((node.right, prefix + "1"))

    return codes

def huffman_frequencies(freq,kept,rare):
    table = {symbol: freq[symbol] for symbol in kept}
    if rare:
        table[ESC] = sum(freq[symbol] for symbol in rare)
    return table

def compress_data(data, p_min):
    freq, probabilities = calculate_probabilities(data)
    kept, rare = split_symbols(probabilities, p_min)

    tree = build_huffman_tree(huffman_frequencies(freq, kept, rare))
    codebook = generate_codes(tree)

    esc_code = codebook.get(ESC, "")
    lookup= {symbol: codebook[symbol] for symbol in kept}
    lookup.update({symbol: esc_code + f"{symbol:08b}" for symbol in rare})

    bit_string = "".join(map(lookup.__getitem__, data))

    metadata = {
        "frequencies": freq,
        "probabilities": probabilities,
        "kept": kept,
        "rare": rare,
        "codebook": codebook,
        "original_length": len(data),
    }

    return bit_string, metadata


