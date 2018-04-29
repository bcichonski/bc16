class BinaryCodeStream:
    def __init__(self):
        bytes = bytearray()
    def emit(self, b):
        self.bytes.extend(b);

class Token:
    def __str__(self):
        return "token";
    def emit(stream):
        pass

class Value(Token):
    def __init__(self, value):
        self.value = value;
    def __str__(self):
        return "value8({})".format(self.value)
    def emit(self, stream):
        super().emit(stream)

class Value8(Value):
    def __str__(self):
        return "value16({})".format(self.value)
    def emit(self, stream):
        stream.emit((self.value >> 4) & 0xf)
        stream.emit(self.value &0xf)

class Register(Token):
