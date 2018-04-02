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
