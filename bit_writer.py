"""bitwriter.py - Member B: pack bits into bytes and read them back."""


class BitWriter:
    """Collects bits and packs them into bytes (MSB first)."""

    def __init__(self):
        self.buffer = bytearray()
        self.current_byte = 0
        self.bit_count = 0       # bits used in current_byte
        self.total_bits = 0      # real bits written (padding excluded)

    def write_bit(self, bit):
        '''Write a single bit (0/1 or "0"/"1").'''
        if bit not in (0, 1, "0", "1"):
            raise ValueError(f"bit must be 0 or 1, got {bit!r}")

        self.current_byte = (self.current_byte << 1) | int(bit)
        self.bit_count += 1
        self.total_bits += 1

        if self.bit_count == 8:
            self.buffer.append(self.current_byte)
            self.current_byte = 0
            self.bit_count = 0

    def write_bits(self, bit_string):
        '''Write a bit string such as "01101".'''
        if bit_string.strip("01"):
            raise ValueError("bit string may only contain 0s and 1s.")

        #finish the current byte if we have a partial byte and the new bits will fill it.
        index = 0
        while self.bit_count and index <len(bit_string):
            self.write_bit(bit_string[index])
            index += 1

        #whole bytes are converted 8 bits at a time
        whole = (len(bit_string)-index) // 8*8
        for start in range(index, index+whole,8):
            self.buffer.append(int(bit_string[start:start+8], 2))
        self.total_bits += whole
        index += whole

        #Leftover (<8) bits stay in current_byte
        while index < len(bit_string):
            self.write_bit(bit_string[index])
            index += 1


    def finish(self):
        '''Pad the last byte with zeros. Returns (payload_bytes, padding_bits).'''
        padding_bits = 0

        if self.bit_count > 0:
            padding_bits = 8 - self.bit_count
            self.buffer.append(self.current_byte << padding_bits)
            self.current_byte = 0
            self.bit_count = 0

        return bytes(self.buffer), padding_bits


class BitReader:
    """Reads packed bytes one bit at a time, ignoring the padding bits."""

    def __init__(self, payload, padding_bits=0):
        if not 0 <= padding_bits <= 7:
            raise ValueError("padding_bits must be between 0 and 7.")
        if padding_bits and not payload:
            raise ValueError("padding given but payload is empty.")

        self.payload = payload
        self.total_bits = len(payload) * 8 - padding_bits
        self.position = 0

    def bits_remaining(self):
        return self.total_bits - self.position

    def read_bit(self):
        '''Return the next valid bit as 0 or 1.'''
        if self.position >= self.total_bits:
            raise EOFError("no more valid bits.")

        byte = self.payload[self.position // 8]
        bit = (byte >> (7 - self.position % 8)) & 1
        self.position += 1
        return bit

    def read_bits(self, count):
        '''Read count bits and return them as an integer.'''
        value = 0
        for _ in range(count):
            value = (value << 1) | self.read_bit()
        return value

    def bit_string(self):
        """All valid (non-padding) bits as a string of 0s and 1s."""
        if not self.payload:
            return ""
        bits= bin(int.from_bytes(self.payload, "big"))[2:].zfill(len(self.payload)*8)
        return bits[:self.total_bits]

    def padding_is_zero(self):
        """true if the unused padding bits at the end are all zero."""
        padding = len(self.payload) *8 - self.total_bits
        return padding == 0 or (self.payload[-1] & ((1 << padding) - 1)) == 0
