"""
Code relative to scanner management.
"""

import gtk
try:
    import sane
    sane.init()
    HAS_SANE = True
except ImportError, e:
    print "Sane support disabled, because of: %s" % (e)
    HAS_SANE = False

class PaperworkScanner(object):
    """
    Handle a scanner. Please note that the scanner init is done in a
    lazy way: We only look for the scanner when the user request a scan.
    """
    def __init__(self):
        # state = (X, Y):
        # X = True/False: True = sane is init ; False = cannot scan
        # Y = reason (string)
        self.__device = None
        self.state = (False, "Sane module not found") # TODO(Jflesch): l10n
        if HAS_SANE:
            self.state = (True, "Can scan") # TODO(Jflesch): l10n

    @staticmethod
    def __look_for_scanner():
        """
        Look for a scanner.

        Returns:
            Returns the corresponding sane device. None if no scanner has been
            found.
        """
        devices = []
        while len(devices) == 0:
            devices = sane.get_devices()
            if len(devices) == 0:
                msg = ("No scanner found (is your scanner turned on ?)."
                       + " Look again ?")
                dialog = gtk.MessageDialog(flags = gtk.DIALOG_MODAL,
                                           type = gtk.MESSAGE_WARNING,
                                           buttons = gtk.BUTTONS_YES_NO,
                                           message_format = msg)
                response = dialog.run()
                dialog.destroy()
                if response == gtk.RESPONSE_NO:
                    raise Exception("No scanner found")

        print "Will use device '%s'" % (str(devices[0]))
        dev = sane.open(devices[0][0])

        try:
            dev.resolution = 300
        except AttributeError, exc:
            print "WARNING: Can't set scanner resolution: " + exc
        try:
            dev.mode = 'Color'
        except AttributeError, exc:
            print "WARNING: Can't set scanner mode: " + exc

        return dev

    def scan(self):
        """
        Run a scan, and returns the corresponding output image.
        """
        if self.__device == None:
            self.__device = self.__look_for_scanner()
        return self.__device.scan()

