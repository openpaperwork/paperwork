# Let's hack


## But first, a few rules

Try to stick to PEP-8 as much as possible. Mainly:

1. Lines are at most 80 characters long
2. Indentation is done using 4 spaces

I don't always do it. Because sometimes I forget the rules or because
sometimes I don't care. Anyway, do as I say, not as I do :)


## Increasing verbose

You can use the environment variable 'PAPERWORK\_VERBOSE' to increase or
decrease the logging level. The accepted values are: DEBUG, INFO, WARNING,
ERROR.


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
  * labels (optional) : a text file containing the labels applied on this document
  * extra.txt (optional) : extra keywords added by the user
* For PDF documents:
  * doc.pdf : the document
  * labels (optional) : a text file containing the labels applied on this document
  * extra.txt (optional) : extra keywords added by the user
  * paper.&lt;X&gt;.words (optional) : A
    [hOCR](https://docs.google.com/document/d/1QQnIQtvdAC_8n92-LhwPcjtAUFwBlzE8EWnKAxlgVf0/preview)
	file, containing all the words found on the page using the OCR. Some PDF contains crap instead
	of the real text, so running the OCR on them can sometimes be useful.

With Tesseract, the hOCR file can be obtained with following command:

	tesseract paper.<X>.jpg paper.<X> -l <lang> hocr && mv paper.<X>.html paper.<X>.words

For example:

	tesseract paper.1.jpg paper.1 -l fra hocr && mv paper.1.html paper.1.words

Here is an example a work directory organisation:

	$ find ~/papers
	/home/jflesch/papers
	/home/jflesch/papers/20130505_1518_00
	/home/jflesch/papers/20130505_1518_00/paper.1.jpg
	/home/jflesch/papers/20130505_1518_00/paper.1.thumb.jpg
	/home/jflesch/papers/20130505_1518_00/paper.1.words
	/home/jflesch/papers/20130505_1518_00/paper.2.jpg
	/home/jflesch/papers/20130505_1518_00/paper.2.thumb.jpg
	/home/jflesch/papers/20130505_1518_00/paper.2.words
	/home/jflesch/papers/20130505_1518_00/paper.3.jpg
	/home/jflesch/papers/20130505_1518_00/paper.3.thumb.jpg
	/home/jflesch/papers/20130505_1518_00/paper.3.words
	/home/jflesch/papers/20130505_1518_00/labels
	/home/jflesch/papers/20110726_0000_01
	/home/jflesch/papers/20110726_0000_01/paper.1.jpg
	/home/jflesch/papers/20110726_0000_01/paper.1.thumb.jpg
	/home/jflesch/papers/20110726_0000_01/paper.1.words
	/home/jflesch/papers/20110726_0000_01/paper.2.jpg
	/home/jflesch/papers/20110726_0000_01/paper.2.thumb.jpg
	/home/jflesch/papers/20110726_0000_01/paper.2.words
	/home/jflesch/papers/20110726_0000_01/extra.txt
	/home/jflesch/papers/20130106_1309_44
	/home/jflesch/papers/20130106_1309_44/doc.pdf
	/home/jflesch/papers/20130106_1309_44/paper.1.words
	/home/jflesch/papers/20130106_1309_44/paper.2.words
	/home/jflesch/papers/20130106_1309_44/labels
	/home/jflesch/papers/20130106_1309_44/extra.txt


## Indexation & Search

The code relative to the indexation and the search is mostly in
[src/paperwork/backend/docsearch.py](src/paperwork/backend/docsearch.py).
Python-Whoosh is used for that and do most of the work.

When starting, Paperwork examine the work directory, and look for
new/modified/deleted documents. It then update automatically its index.

The index is stored in ~/.local/share/paperwork/index.


## Code organisation

The code is splited in two pieces:
* backend : Everything related to document management. May depend on various things but *not* Gtk
* frontend : The GUI. Entirely dependant on Gtk


## Thread safety

Thread safety is a major issue in Paperwork. We need threads to keep the GUI
smooth, but unfortunately, a lot of Paperwork dependencies are not
thread-safe. For instance, libpoppler is not thread-safe at all.

A job scheduling mechanism has been implemented (see
src/paperwork/frontend/jobs.py):

Each Job represents ... well, a job to do. Some jobs can be stopped and resumed
later (for instance JobDocThumbnailer).

JobFactories instanciate Jobs. They are also used to keep the job recognizable.

Each JobScheduler represent a thread. It accepts jobs (using the method
schedule()). The job with the higher priority is run first. If the job
added to the scheduler has an higher priority than the active one,
the scheduler will *try* to stop the active one and run it back later.

Jobs can be cancelled (assuming they are stoppable or not active yet). A single
job can be cancelled, or all the jobs from a given factory.

There is one main scheduler (called 'main'), and some others used mostly for
progress bar updates based on time. The main scheduler is the one used to
access all the documents contents and the index.

Note that there are other threads running: The thread of
[PyInsane](https://github.com/jflesch/pyinsane#readme) and the Gtk main loop.


## Tips

If you want to make changes, here are few things that can help you:

1. Paperwork looks for a 'paperwork.conf' in the current work directory before
   looking for a '.paperwork.conf' in your home directory. So if you want to
   use a different config and/or a different set of documents for development
   than for your real-life work, just copy your '~/.paperwork.conf' to
   './paperwork.conf'. Note that the settings dialog will also take care of
   updating './paperwork.conf' instead of '~/.paperwork.conf'.
2. "pep8" is your friend
3. "pylint" is your friend: $ cd src ; pylint --rcfile=../pylintrc \*
