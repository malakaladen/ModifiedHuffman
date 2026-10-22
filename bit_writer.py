class BitWriter:
    def __init__(self):
        self.data = bytearray()
        self.current_byte = 0
        self.used_bits = 0
        self.bit_count = 0

    def write_bit(self, bit):
        '''Add one bit to the current byte.'''
        if bit not in (0, 1, "0", "1"):
            raise ValueError("bit must be 0 or 1.")

        self.current_byte = (self.current_byte << 1) | int(bit)
        self.used_bits += 1
        self.bit_count += 1

        if self.used_bits == 8:
            self.data.append(self.current_byte)
            self.current_byte = 0
            self.used_bits = 0

    def write_bits(self, bits):
        '''Write a sequence of bits.'''
        for bit in bits:
            self.write_bit(bit)

    def finish(self):
        '''Return the packed bytes and number of padding bits.'''
        data = bytearray(self.data)
        padding_bits = (8 - self.used_bits) % 8

        #Pad the final byte with zeros.
        if self.used_bits:
            data.append(self.current_byte << padding_bits)

        return bytes(data), padding_bits


class BitReader:
    def __init__(self, data, padding_bits=0):
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes.")

        if type(padding_bits) is not int or not 0 <= padding_bits <= 7:
            raise ValueError("padding_bits must be between 0 and 7.")

        if not data and padding_bits:
            raise ValueError("empty data cannot contain padding.")

        if padding_bits and data[-1] & ((1 << padding_bits) - 1):
            raise ValueError("padding bits must be zero.")

        self.data = data
        self.total_bits = len(data) * 8 - padding_bits
        self.position = 0

    def read_bit(self):
        '''Read one bit, or return None at the end.'''
        if self.position >= self.total_bits:
            return None

        byte_index = self.position // 8
        bit_index = 7 - self.position % 8

        bit = (self.data[byte_index] >> bit_index) & 1
        self.position += 1

        return bit

    def read_bits(self, count):
        '''Read a fixed number of bits as a string.'''
        if type(count) is not int or count < 0:
            raise ValueError("count must be a non-negative integer.")

        if self.position + count > self.total_bits:
            raise EOFError("not enough bits remaining.")

        bits = []

        for _ in range(count):
            bits.append(str(self.read_bit()))

        return "".join(bits)
