import gtk

from util import load_uifile

class Tag(object):
    def __init__(self, name = "", color = "#000000000000"):
        self._name = name
        self._color = gtk.gdk.color_parse(color)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self._color = color

    def tag_cmp(self, other):
        return cmp(self._name, other._name)
    def __lt__(self, other):
        return self.tag_cmp(other) < 0
    def __gt__(self, other):
        return self.tag_cmp(other) > 0
    def __eq__(self, other):
        return self.tag_cmp(other) == 0
    def __le__(self, other):
        return self.tag_cmp(other) <= 0
    def __ge__(self, other):
        return self.tag_cmp(other) >= 0
    def __ne__(self, other):
        return self.tag_cmp(other) != 0
    def get_html_color(self):
        return ("#%02X%02X%02X" % (self._color.red >> 8, self._color.green >> 8, self._color.blue >> 8))
    def get_color_str(self):
        return self.color.to_string()
    def __str__(self):
        return unicode("<span bgcolor=\"%s\">    </span> %s" % (self.get_html_color(), self.name))

class TagEditor(object):
    def __init__(self, tagToEdit = None):
        if tagToEdit == None:
            tagToEdit = Tag()
        self._tag = tagToEdit

    def edit(self, mainWindow):
        wTree = load_uifile("tagedit.glade")

        dialog = wTree.get_object("dialogTagEditor")
        nameEntry = wTree.get_object("entryTagName")
        colorChooser = wTree.get_object("colorselectionTagColor")

        nameEntry.set_text(self._tag.name)
        colorChooser.set_current_color(self._tag.color)

        dialog.set_transient_for(mainWindow)
        dialog.add_button("Cancel", gtk.RESPONSE_CANCEL)
        dialog.add_button("Ok", gtk.RESPONSE_OK)
        response = dialog.run()
    
        if ( response == gtk.RESPONSE_OK ) and nameEntry.get_text().strip() == "":
            response = gtk.RESPONSE_CANCEL
        if ( response == gtk.RESPONSE_OK ):
            print "Tag validated"
            self._tag.name = nameEntry.get_text()
            self._tag.color = colorChooser.get_current_color()
        else:
            print "Tag editing cancelled"

        dialog.destroy()

        print "Tag after editing: %s" % (self._tag)
        return (response == gtk.RESPONSE_OK)

    @property
    def tag(self):
        return self._tag

