import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['new_doc']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.new_doc = None

    def config_put(self, opt, value, *args, **kwargs):
        if opt != "workdir":
            return None
        # Bug report 170: When the work directory has been changed,
        # we have to make sure to drop any reference to it so the user doesn't
        # use it by accident.
        # (keep in mind that self.new_doc = (doc_id, doc_url), and doc_url
        # includes the work directory path)
        self.new_doc = None
        return None

    def get_new_doc(self):
        if self.new_doc is not None:
            if self.core.call_success("is_doc", self.new_doc[1]) is None:
                return self.new_doc
        self.new_doc = self.core.call_success("storage_get_new_doc")
        return self.new_doc
