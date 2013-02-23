from gi.repository import Gtk

from paperwork.util import load_uifile


class LabelEditor(object):
    """
    Dialog to create / edit labels
    """

    def __init__(self, label_to_edit=None):
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
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Ok", Gtk.ResponseType.OK)
        response = dialog.run()

        if (response == Gtk.ResponseType.OK
            and name_entry.get_text().strip() == ""):
            response = Gtk.ResponseType.CANCEL
        if (response == Gtk.ResponseType.OK):
            print "Label validated"
            self.label.name = unicode(name_entry.get_text())
            self.label.color = color_chooser.get_current_color()
        else:
            print "Label editing cancelled"

        dialog.destroy()

        print "Label after editing: %s" % (self.label)
        return (response == Gtk.ResponseType.OK)
