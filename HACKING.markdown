# Let's hack


## But first, a few rules

Try to stick to PEP-8 as much as possible. Mainly:

1. Lines are at most 80 characters long
2. Indentation is done using 4 spaces

I don't always do it. Because sometimes I forget the rules or because
sometimes I don't care. Anyway, do as I say, not as I do :)


## Documents organisation

workdir|rootdir = ~/papers

In the work directory, you have folders, one per document.

The folder names are (usually) the scan/import date of the document:
YYYYMMDD\_hhmm\_ss[\_&lt;idx&gt;]. The suffix 'idx' is optional and is just
a number added in case of name collision.

In every folder you have:

* For image documents:
  * paper.&lt;X&gt;.jpg : A page in JPG format (X starts at 1)
  * paper.&lt;X&gt;.words : A
    [hOCR](https://docs.google.com/document/d/1QQnIQtvdAC_8n92-LhwPcjtAUFwBlzE8EWnKAxlgVf0/preview)
	file, containing all the words found on the page using the OCR.
  * paper.&lt;X&gt;.thumb.jpg (optional) : A thumbnail version of the page (faster to load)
  * labels : a text file containing the labels applied on this document
* For PDF documents:
  * doc.pdf : the document
  * labels : a text file containing the labels applied on this document

With Tesseract, the hOCR file can be obtained with following command:

	tesseract paper.&lt;X&gt;.jpg paper.&lt;X&gt; -l &lt;lang&gt; hocr && mv paper.&lt;X&gt;.html paper.&lt;X&gt;.words

For example:

	tesseract paper.1.jpg paper.1 -l fra hocr && mv paper.1.html paper.1.words


## Indexation & Search

The code relative to the indexation and the search is mostly in [src/paperwork/backend/docsearch.py](src/paperwork/backend/docsearch.py).

When starting, Paperwork examine the work directory, and look for new/modified/deleted documents. It then update the index.

The index is stored in ~/.local/share/paperwork/index.


## Code organisation

The code is splited in two pieces:
* backend : Everything related to document management. May depend on various things but *not* Gtk
* frontend : The GUI. Entirely dependant on Gtk


## Thread safety

Thread safety is a major issue in Paperwork. We need threads to keep the GUI
smooth, but unfortunately, a lot of Paperwork dependencies are not
thread-safe. For instance, libpoppler is not thread-safe at all.

As a compromise (aka "workaround"), a mechanism called
["workers"](src/paperwork/frontend/workers.py) has been implemented in
Paperwork.

The basic idea is to have 2 main threads: One where the gobject main loop is
running, and one doing pretty much any non-GUI-related tasks, called
"WorkerThread". This WorkerThread keep running jobs from a queue. Each task
or job we want to do outside of the gobject main loop is handled by a Worker.
When started, the Worker will actually register itself in the WorkerThread.
The WorkerThread will then run the do() method of each registered Worker().

Some Workers can be halted. Some Workers can be interrupted and restarted
later. When a Worker register itself in the WorkerThread, if the
currently-running Worker can be interrupted, the WorkerThread will interrupt
it and put it back at the end of the Worker queue. The idea here is to try
to keep the GUI as reactive as possible.

There are also IndependantWorkers. There are simply using their own thread.

Note that there is another thread running: The thread of
[PyInsane](https://github.com/jflesch/pyinsane#readme).


## Tips

If you want to make changes, here are few things that can help you:

1. You don't need to install paperwork to run it. Just run 'src/paperwork.py' (do not run 'cd src ; ./paperwork.py' ! Otherwise Paperwork won't use the correct glade files).
2. Paperwork looks for a 'paperwork.conf' in the current work directory before
   looking for a '.paperwork.conf' in your home directory. So if you want to
   use a different config and/or a different set of documents for development
   than for your real-life work, just copy your '~/.paperwork.conf' to
   './paperwork.conf'. Note that the settings dialog will also take care of
   updating './paperwork.conf' instead of '~/.paperwork.conf'.
3. "pep8" is your friend
4. "pylint" is your friend: $ cd src ; pylint --rcfile=../pylintrc \*
