## Description

[Paperwork](https://github.com/jflesch/paperwork#readme) is a GUI to make papers searchable.

This is the backend part of Paperwork. It manages:
- The work directory / Access to the documents
- Indexing
- Searching
- Suggestions
- Import
- Export

There is no GUI here. The GUI is https://github.com/jflesch/paperwork .

Regarding the name "Paperwork", it can refer to both the GUI or the backend. If you want to be specific, you can call the gui "paperwork-gui" instead of just Paperwork.

## Dependencies

* [Pillow](https://pypi.python.org/pypi/Pillow/): Image manipulation (with JPEG support)
* [Whoosh](https://pypi.python.org/pypi/Whoosh/): To index and search documents, and provide keyword suggestions
* Libpoppler (PDF support)
* Cairo
* Gobject Introspection


## Usage

You can find some examples in scripts/. You can also look at the code of [Paperwork](https://github.com/jflesch/paperwork#readme) for reference.

Here are some snippets:

```py
import paperwork_backend.config as config
import paperwork_backend.docsearch as docsearch

pconfig = config.PaperworkConfig()
pconfig.read()

print ("Opening docs ({})".format(pconfig.settings['workdir'].value))

# Instantiating a DocSearch object will open the indexes and the label
# bayesian filter caches. It may take a few seconds
docsearch = docsearch.DocSearch(pconfig.settings['workdir'].value)

suggestions = docsearch.find_suggestions(u"flesh")
print ("Keyword suggestions: {}".format(suggestions))
# [u'cles', u'flesc', u'flesch', u'jflesch', u'les']

documents = docsearch.find_documents(u"flesch")
print ("Nb document found: {}".format(len(documents))
# 1064

doc = documents[0]
print ("Nb pages of the first doc: {}".format(doc.nb_pages))
# 2

page = doc.pages[0]
print ("First page content:\n{}".format(page.text))
# [u'Salaires - D\xe9clarant 1',
# u'PPE - temps plein - D\xe9clarant 1',
# (...)
# u'/PZwpNYBAIPdsSiwBRqb0NXv/7bBPLHFI1JTvg==']

print ("Page size: {}".format(page.size))
# (1190, 1682)

print ("Page PIL Image object: {}".format(page.img))
# <PIL.Image.Image image mode=RGB size=1190x1682 at 0x7F4A561FA8C0>
```

## Contact/Help

Developement is strongly related to Paperwork-gui.

* [Mailing-list](https://github.com/jflesch/paperwork/wiki/Contact#mailing-list)
* [Extra documentation / FAQ / Tips / Wiki](https://github.com/jflesch/paperwork-backend/wiki)
* [Bug trackers](https://github.com/jflesch/paperwork/wiki/Contact#bug-trackers)


## Contact

* [Mailing-list](https://github.com/jflesch/paperwork/wiki/Contact#mailing-list)
* [Bug tracker](https://github.com/jflesch/paperwork/issues/)


## Licence

GPLv3 or later. See LICENSE.


## Development

Developement is strongly related to Paperwork-gui.
All the information can be found on [the wiki](https://github.com/jflesch/paperwork/wiki#for-developers)
