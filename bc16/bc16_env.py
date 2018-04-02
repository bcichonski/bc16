class Environment:
    def __init__(self, debug = False):
        self.debug = debug
    def log(self, msg):
        if self.debug:
            print("[DBG]:"+msg)
