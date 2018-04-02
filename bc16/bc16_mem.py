class MemBus:
    def __init__(self, env, size):
        self.env = env
        self.size = size
        self.mem = bytearray(size)
    def write_byte(self, addr, byte):
        self.mem[addr] = byte
        self.env.log("MEM WRITE AT 0x{0:x} VAL 0x{1:x}".format(addr, byte)) 
    def read_byte(self, addr):
        val = self.mem[addr]
        self.env.log("MEM READ AT 0x{0:x} VAL 0x{1:x}".format(addr, val))
        return val
