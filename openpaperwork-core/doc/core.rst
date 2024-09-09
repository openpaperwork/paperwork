Core & Plugins
==============


Basic concepts
--------------

The idea behind OpenPaperwork's plugins got inspired by
`Python duck typing <https://en.wikipedia.org/wiki/Duck_typing>`_: When you
request something, it does not matter who does the job as long as it's done.


To that end, when the calling code wants something done, it uses the
core. It provides a callback name and some arguments. It does not know which
plugin will handle this call (nor if one will) and it doesn't matter to them
as long as the job is done. The core will take care of calling the corresponding
callbacks.

Many plugins can provide the same callback names but with different
implementations.

Calling code can:

* call all the callbacks with a given name one after the
  other: :py:meth:`~openpaperwork_core.Core.call_all`,
* call them until one of them reply with a value !=
  `None`: :py:meth:`~openpaperwork_core.Core.call_success`,
* or call just one of them semi-randomly:
  :py:meth:`~openpaperwork_core.Core.call_one`.

A plugin is a Python module containing a class named `Plugin` (subclassing
:py:class:`~openpaperwork_core.PluginBase`). This class must be
instantiable without arguments.
Callbacks are all the methods provided by those classes `Plugin`
(with some exceptions, like methods starting with `_` and those coming from
:py:class:`~openpaperwork_core.PluginBase`).

Each plugin can implement many interfaces. Those interfaces are used to define
dependencies and are simply conventions: Plugins pretending to implement some
interfaces should implement the corresponding methods but no check is done to
ensure they do.


Examples
--------

.. toctree::
   example_plugin
   example_app


API
---

You're strongly advised to read the documentation of
:py:meth:`~openpaperwork_core.Core.call_all`, :py:meth:`~openpaperwork_core.Core.call_success`, :py:meth:`~openpaperwork_core.Core.call_one`.

.. toctree::
   core_api
