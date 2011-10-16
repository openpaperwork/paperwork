"""
Code to manage document labels
"""

import gtk

from util import load_uifile

class Label(object):
    """
    Represents a Label (color + string).
    """

    def __init__(self, name = "", color = "#000000000000"):
        """
        Arguments:
            name --- label name
            color --- label color (string representation, see get_color_str())
        """
        self.name = name
        self.color = gtk.gdk.color_parse(color)

    def __label_cmp(self, other):
        """
        Comparaison function. Can be used to sort labels alphabetically.
        """
        return cmp(self.name, other.name)
    def __lt__(self, other):
        return self.__label_cmp(other) < 0
    def __gt__(self, other):
        return self.__label_cmp(other) > 0
    def __eq__(self, other):
        return self.__label_cmp(other) == 0
    def __le__(self, other):
        return self.__label_cmp(other) <= 0
    def __ge__(self, other):
        return self.__label_cmp(other) >= 0
    def __ne__(self, other):
        return self.__label_cmp(other) != 0
    def get_html_color(self):
        """
        get a string representing the color, using HTML notation
        """
        return ("#%02X%02X%02X" % (self.color.red >> 8, self.color.green >> 8,
                                   self.color.blue >> 8))
    def get_color_str(self):
        """
        Returns a string representation of the color associated to this label.
        """
        return self.color.to_string()
    def __str__(self):
        return ("<span bgcolor=\"%s\">    </span> %s" % (self.get_html_color(),
                                                         self.name))

class LabelEditor(object):
    """
    Dialog to create / edit labels
    """

    def __init__(self, label_to_edit = None):
        if label_to_edit == None:
            label_to_edit = Label()
        self.label = label_to_edit

    def edit(self, main_window):
        """
        Open the edit dialog, and update the label according to user changes
        """
        widget_tree = load_uifile("labeledit.glade")

        dialog = widget_tree.get_object("dialogLabelEditor")
        name_entry = widget_tree.get_object("entryLabelName")
        color_chooser = widget_tree.get_object("colorselectionLabelColor")

        name_entry.set_text(self.label.name)
        color_chooser.set_current_color(self.label.color)

        dialog.set_transient_for(main_window)
        dialog.add_button("Cancel", gtk.RESPONSE_CANCEL)
        dialog.add_button("Ok", gtk.RESPONSE_OK)
        response = dialog.run()
    
        if (response == gtk.RESPONSE_OK
            and name_entry.get_text().strip() == ""):
            response = gtk.RESPONSE_CANCEL
        if (response == gtk.RESPONSE_OK):
            print "Label validated"
            self.label.name = name_entry.get_text()
            self.label.color = color_chooser.get_current_color()
        else:
            print "Label editing cancelled"

        dialog.destroy()

        print "Label after editing: %s" % (self.label)
        return (response == gtk.RESPONSE_OK)

