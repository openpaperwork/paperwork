Synchronizations
================

Some plugins must do some actions when some documents are created,
modified, or deleted (page cropping, OCR, etc). Many plugins need to maintain
indexes (search engine, label guessing, etc) up-to-date compared to the user
work directory.

Moreover, external tools like Nextcloud Desktop synchronization may also update
the work directory, and those changes must be taken into account too.

In Paperwork, those processes of taking into account changes in the work directory
are called "synchronizations".


Prerequisites
-------------

You must understand how `openpaperwork_core.Core` works and how plugins
communicate through the core.


Reference implementation
------------------------

You can have a look at `paperwork_backend.shell_hooks` to have some idea of
how plugins must handle synchronizations.


Transactions
------------

To get notified of those changes, first, plugins must define a transaction class.
This class should inherit `paperwork_backend.sync.BaseTransaction`:

- `add_doc()` is called for each new document
- `del_doc()` is called for each deleted document
- `upd_doc()` is called for each modified document
- `commit()` is called at the end of the sync if everything went well
- `cancel()` is called at the end of the sync if something crashed


Synchronization on user actions
-------------------------------

For reference, see `paperwork_backend.sync.Plugin.transaction_simple()`.

When the user modifies/create/delete a document, the synchronization process is
fairly straightforward. This process is only for changes
done to documents by a component inside Paperwork.

The calling code (the one that did the doc modification) calls all the callbacks
`doc_transaction_start()` to collect all the transactions from all the plugins.

It will then call the methods of each transaction objects as required.


.. uml::

   caller -> paperwork_backend.sync: transaction_simple()
   paperwork_backend.sync -> "plugin A": doc_transaction_start()
   paperwork_backend.sync <- "plugin A": returns Plugin A Transaction
   paperwork_backend.sync -> "plugin B": doc_transaction_start()
   paperwork_backend.sync <- "plugin B": returns Plugin B Transaction
   paperwork_backend.sync -> "plugin A": Plugin A Transaction.add_doc()
   paperwork_backend.sync -> "plugin B": Plugin B Transaction.add_doc()
   paperwork_backend.sync -> "plugin A": Plugin A Transaction.del_doc()
   paperwork_backend.sync -> "plugin B": Plugin B Transaction.del_doc()
   paperwork_backend.sync -> "plugin A": Plugin A Transaction.commit()
   paperwork_backend.sync -> "plugin B": Plugin B Transaction.commit()


Global synchronization
----------------------

For reference, see `paperwork_backend.sync.Plugin.transaction_sync_all()`.

Global synchronization is run every time `paperwork-gtk` is started or when
`paperwork-cli sync` is called. Those global synchronizations are here to take
into account changes done by third-party software (Nextcloud Desktop, Syncthing,
etc).

All `sync()` methods are called to fetch the synchronization promises
from all plugins supporting it.


Document tracker
~~~~~~~~~~~~~~~~

One of those plugins is `paperwork_backend.sync.doctracker`.
Other plugins can register in `doctracker` plugin by calling `doc_tracker_register()`.
When `sync()` will be called, `doctracker` will take care of:

- figuring out which documents in the work directory have changed.
- calling the transactions of all the plugins that registered to it.


.. uml::

   == Initialization ==
   "plugin A" -> doctracker: doc_tracker_register(transaction factory)
   "plugin B" -> doctracker: doc_tracker_register(transaction factory)


.. uml::

   == Synchronization ==
   "paperwork-cli sync" -> paperwork_backend.sync: transaction_sync_all()
   paperwork_backend.sync -> doctracker: sync()
   activate doctracker
   doctracker -> "plugin A": make transaction
   doctracker <- "plugin A": returns Plugin A Transaction()
   doctracker -> "plugin B": make transaction
   doctracker <- "plugin B": returns Plugin B Transaction()
   doctracker -> doctracker: examine work directory
   activate doctracker
   doctracker -> "plugin A": Plugin A Transaction.add_doc()
   doctracker -> "plugin B": Plugin B Transaction.add_doc()
   doctracker -> "plugin A": Plugin A Transaction.del_doc()
   doctracker -> "plugin B": Plugin B Transaction.del_doc()
   doctracker -> "plugin A": Plugin A Transaction.commit()
   doctracker -> "plugin B": Plugin B Transaction.commit()
   deactivate doctracker
   deactivate doctracker


Page tracker
~~~~~~~~~~~~

Another plugin used for synchronizations is `paperwork_backend.sync.pagetracker`.
This plugin is useful for other plugins needing to know exactly which pages have
changed (OCR plugin, cropping plugin, etc).
