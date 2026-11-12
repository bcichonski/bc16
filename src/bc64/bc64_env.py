import os.path
import re
import sys

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
    def __init__(self, debug = True):
        self.debug = debug
    def log(self, msg):
        if self.debug:
            print("[DBG]:"+msg)
    def get_string(self, prompt):
        res = input("]> "+prompt)
        return res
    def open_file_to_read(self, filename):
        return open(filename, "rb")
    def open_file_to_write(self, filename):
        return open(filename, "wb")
    def open_file_to_readwrite(self, filename):
        return open(filename, "r+b")
    def move_file_handle(self, handle, position):
        handle.seek(position)
    def close_file(self, handle):
        handle.close()
    def read_byte(self, handle):
        return handle.read(1)
    def write_byte(self, handle, byte):
        handle.write(byte.to_bytes(1, 'big'))
    def read_bytes(self, handle, size):
        return handle.read(size)
    def write_bytes(self, handle, bytes):
        res = handle.write(bytes)
        handle.flush()
        return res
    def file_exists(self, name):
        return os.path.exists(name)
    def get_char(self):
        return getch()
    def write_char(self,byte):
        print(chr(byte), end='', flush=True)


class EndOfInput(BaseException):
    """Raised by ScriptedEnvironment when the scripted input has no more bytes."""


class ScriptedEnvironment(Environment):
    """Headless host layer: every feature is optional and independent.

    disk_a / disk_b: image paths answered to the 'Disk X name:' prompt (no stdin, no echo).
    tape_dir: directory in which relative *.btap names are resolved.
    input_source: path of a script file, '-' for stdin, or a binary file-like object.
        Line endings (LF, CR LF, CR) are delivered as a single CR.
    output_path: file receiving every printer byte (also still printed to stdout).
    """
    ENTER = 0x0d
    DISK_PROMPT = re.compile(r"^Disk ([AB]) name:$")

    def __init__(self, debug = True, disk_a = None, disk_b = None, tape_dir = None,
                 input_source = None, output_path = None):
        super().__init__(debug)
        self.disks = {'A': disk_a, 'B': disk_b}
        self.tape_dir = tape_dir
        self.input = None
        self.own_input = False
        if input_source == '-':
            self.input = sys.stdin.buffer
        elif isinstance(input_source, (str, os.PathLike)):
            self.input = open(input_source, "rb")
            self.own_input = True
        else:
            self.input = input_source
        self.pushback = None
        self.output = open(output_path, "wb") if output_path is not None else None

    def close(self):
        if self.output is not None:
            self.output.close()
            self.output = None
        if self.own_input and self.input is not None:
            self.input.close()
            self.input = None

    def _read_raw(self):
        if self.pushback is not None:
            b = self.pushback
            self.pushback = None
            return b
        return self.input.read(1)

    def _next_byte(self):
        """Next script byte (line endings folded into one CR), or None at end."""
        b = self._read_raw()
        if not b:
            return None
        value = b[0]
        if value == 0x0d:
            nxt = self._read_raw()
            if nxt and nxt[0] != 0x0a:
                self.pushback = nxt
            return self.ENTER
        if value == 0x0a:
            return self.ENTER
        return value

    def _read_line(self):
        chars = []
        while True:
            value = self._next_byte()
            if value is None:
                if not chars:
                    raise EndOfInput()
                break
            if value == self.ENTER:
                break
            chars.append(value)
        return bytes(chars).decode("latin-1")

    def get_string(self, prompt):
        match = ScriptedEnvironment.DISK_PROMPT.match(prompt)
        if match and self.disks[match.group(1)] is not None:
            return self.disks[match.group(1)]
        if self.input is not None:
            return self._read_line()
        return super().get_string(prompt)

    def get_char(self):
        if self.input is None:
            return super().get_char()
        value = self._next_byte()
        if value is None:
            raise EndOfInput()
        return chr(value)

    def write_char(self, byte):
        super().write_char(byte)
        if self.output is not None:
            self.output.write(bytes([byte & 0xff]))
            self.output.flush()

    def _resolve(self, name):
        if self.tape_dir is not None and name.endswith(".btap") and not os.path.isabs(name):
            return os.path.join(self.tape_dir, name)
        return name

    def open_file_to_read(self, filename):
        return super().open_file_to_read(self._resolve(filename))

    def open_file_to_write(self, filename):
        return super().open_file_to_write(self._resolve(filename))

    def open_file_to_readwrite(self, filename):
        return super().open_file_to_readwrite(self._resolve(filename))

    def file_exists(self, name):
        return super().file_exists(self._resolve(name))
