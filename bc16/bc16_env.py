# from https://github.com/joeyespo/py-getch
try:
    from msvcrt import getch
except ImportError:
    def getch():
        """
        Gets a single character from STDIO.
        """
        import sys
        import tty
        import termios
        fd = sys.stdin.fileno()
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            old = termios.tcgetattr(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
# end from

class Environment:
    def __init__(self, debug = False):
        self.debug = debug
    def log(self, msg):
        if self.debug:
            print("[DBG]:"+msg)
    def get_string(self, prompt):
        res = raw_input("]> "+prompt)
        return res
    def open_file_to_read(self, filename):
        return open(filename, "rb")
    def open_file_to_write(self, filename):
        return open(filename, "wb")
    def close_file(self, handle):
        handle.close()
    def read_byte(self, handle):
        return handle.read(1)
    def write_byte(self, handle, byte):
        handle.write(byte.to_bytes(1, 'big'))
    def get_char(self):
        return getch()
    def write_char(self,byte):
        print(chr(byte), end='')
