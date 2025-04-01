from . import PluginBase


class Plugin(PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['urls']

    def url_args_join(self, *args, **kwargs):
        out = "".join(args)
        if len(kwargs) <= 0:
            return out
        first = True
        for (k, v) in sorted(list(kwargs.items())):
            if v is None:
                continue
            if first:
                out += "#"
                first = False
            else:
                out += "&"
            out += "{}={}".format(k, v)
        return out

    def url_args_split(self, url):
        if "#" not in url:
            return (url, {})
        (base, kwargs) = url.split("#", 1)
        kwargs = kwargs.split("&")
        out = {}
        for kwarg in kwargs:
            (k, v) = kwarg.split("=", 1)
            out[k] = v
        return (base, out)
