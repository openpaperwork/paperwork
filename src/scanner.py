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

class PaperworkScannerException(Exception):
    """
    Exception raised in case we try to use an invalid scanner configuration
    """
    def __init__(self, message):
        Exception.__init__(self, message)

class PaperworkScanner(object):
    """
    Handle a scanner. Please note that the scanner init is done in a
    lazy way: We only look for the scanner when the user request a scan.
    """

    CALIBRATION_RESOLUTION = 150
    POSSIBLE_RESOLUTIONS = [ 100, 200, 300, 400, 500, 600 ]
    RECOMMENDED_RESOLUTION = 300

    def __init__(self):
        self.__available_devices = []   # see sane.get_devices()
        # selected_device: one value from self.__available_devices[][0] (scanner
        # id)
        self.__selected_device = None
        self.selected_resolution = self.RECOMMENDED_RESOLUTION
        # active_device: tuple: (value from __available_devices[][0], result from sane.open())
        self.__active_device = None

        # state = (X, Y):
        # X = True/False: True = sane is init and a scanner is selected ; False = cannot scan
        # Y = Scan action status (string)
        self.state = (False, "No scanner set")

    def __get_available_devices(self):
        self.__available_devices = sane.get_devices()
        return self.__available_devices

    available_devices = property(__get_available_devices)

    def __get_selected_device(self):
        return self.__selected_device

    def __set_selected_device(self, selected):
        # TODO(Jflesch): l10n
        if not HAS_SANE:
            self.state = (False, "Sane module not found")
        elif not selected:
            self.state = (False, "No scanner has been selected")
        else:
            self.state = (True, "Scan new page")
        self.__selected_device = selected

    selected_device = property(__get_selected_device, __set_selected_device)

    def __open_scanner(self):
        """
        Look for the selected scanner.

        Returns:
            Returns the corresponding sane device. None if no scanner has been
            found.
        """
        if not self.__selected_device:
            if self.__active_device:
                self.__active_device[1].close()
            self.__active_device = None
            raise PaperworkScannerException("No scanner selected")

        if self.__active_device and self.__selected_device == self.__active_device[0]:
            # already opened
            return
    
        if self.__active_device:
            self.__active_device[1].close()
            self.__active_device = None

        while self.__active_device == None:
            for device in self.available_devices:
                if device[0] == self.__selected_device:
                    print "Will use device '%s'" % (str(device))
                    dev_obj = sane.open(device[0])
                    self.__active_device = (device[0], dev_obj)
                    return

            msg = ("No scanner found (is your scanner turned on ?)."
                   + " Look again ?")
            dialog = gtk.MessageDialog(flags=gtk.DIALOG_MODAL,
                                       type=gtk.MESSAGE_WARNING,
                                       buttons=gtk.BUTTONS_YES_NO,
                                       message_format=msg)
            response = dialog.run()
            dialog.destroy()
            if response == gtk.RESPONSE_NO:
                raise PaperworkScannerException("No scanner found")

    def __set_scanner_settings(self):
        try:
            self.__active_device[1].resolution = self.selected_resolution
        except AttributeError, exc:
            print "WARNING: Can't set scanner resolution: " + exc
        try:
            self.__active_device[1].mode = 'Color'
        except AttributeError, exc:
            print "WARNING: Can't set scanner mode: " + exc

    def scan(self):
        """
        Run a scan, and returns the corresponding output image.
        """
        self.__open_scanner()
        self.__set_scanner_settings()
        return self.__active_device[1].scan()

    def close(self):
        if self.__active_device != None:
            self.__active_device[1].close()
            self.__active_device = None
