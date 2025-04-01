Plugin Example
==============


.. code-block:: python

    import openpaperwork_core

    class Plugin(openpaperwork_core.PluginBase):
        # callbacks will always be run before those of priority <= 21
        # but after those of priority >= 23
        PRIORITY = 22

        @classmethod
        def get_interfaces(cls):
           # indicates which interfaces this plugin satisfies.
           # note that this is only used for controlling that dependencies are
           # satisfied (see get_deps()). There are no checks at all to ensure
           # that the methods corresponding to each interface are actually
           # implemented.
           return ['interface_name_toto', 'interface_name_tutu']

        @classmethod
        def get_deps(cls):
            # specify that we are looking for plugins implementing the
            # specified interface(s).
            # Provide also some default plugins to load if no plugins provide
            # the requested interface yet.
            # Note that plugins may be loaded in any order. Dependencies may
            # not be satisfied yet when they are loaded.
            # When initializing plugins, the core will make sure that
            # all dependencies are satisfied, loaded and initialized before
            # calling the method `init()` of this plugin.
            return [
                {
                    'interface': 'interface_name_a',
                    'defaults': [
                        'suggested_default_plugin_a',
                        'suggested_default_plugin_b',
                    ],
                },
                {
                   'interface': 'inteface_name_b',
                    'defaults': [
                        'suggested_default_plugin_d',
                        'suggested_default_plugin_e',
                    ],
                }
            ]

        def __init__(self, core):
            super().__init__(core)
            # all the dependencies have loaded and initialized.
            # we can safely rely on them here.

        def some_method_a(self, arg_a):
            # do something
            self.core.call_all("some_method_of_other_plugins", "arg_a", 22)
