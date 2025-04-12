import abc


g_singletons = {}


def reset_singletons():
    global g_singletons
    g_singletons = {}


class Singleton(abc.ABCMeta):
    """
    To be used as a metaclass to turn it into a singleton.
    """
    def __call__(cls, *args, **kwargs):
        instance = g_singletons.get(cls)
        if instance is None:
            instance = super().__call__(*args, **kwargs)
            g_singletons[cls] = instance
        return instance
