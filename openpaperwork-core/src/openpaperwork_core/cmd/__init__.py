class DummyConsole:
    def clear(self, *args, **kwargs):
        pass

    def print(self, *args, **kwargs):
        pass

    def input(self, prompt=""):
        return None
