"""
Code relative to scanner management.
"""

import gettext
import gtk
import tesseract
try:
    import sane
    sane.init()
    HAS_SANE = True
except ImportError, e:
    print "Sane support disabled, because of: %s" % (e)
    HAS_SANE = False

_ = gettext.gettext


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

    RECOMMENDED_RESOLUTION = 300
    CALIBRATION_RESOLUTION = 200

    def __init__(self):
        self.__available_devices = []   # see sane.get_devices()
        # selected_device: one value from self.__available_devices[][0]
        # (scanner id)
        self.__selected_device = None
        self.selected_resolution = self.RECOMMENDED_RESOLUTION
        # active_device: tuple: (value from __available_devices[][0], result
        # from sane.open())
        self.__active_device = None

        # state = (X, Y):
        # X = True/False: True = sane is init and a scanner is selected
        #   ; False = cannot scan
        # Y = Scan action status (string)
        self.state = (False, "No scanner set")

    def __get_available_devices(self):
        """
        Return the list of available scan devices (array)
        """
        self.__available_devices = sane.get_devices()
        return self.__available_devices

    available_devices = property(__get_available_devices)

    def __get_selected_device(self):
        """
        Return the device id selected by the user for scanning
        """
        return self.__selected_device

    def __set_selected_device(self, selected):
        """
        Set the device id selected by the user
        """
        if not HAS_SANE:
            self.state = (False, _('Sane module not found'))
        elif not tesseract.is_tesseract_available():
            self.state = (False,
                          _('Tesseract is not available. Can\'t do OCR'))
        elif not selected:
            self.state = (False, _('No scanner has been selected'))
        else:
            self.state = (True, _('Scan new page'))
        self.__selected_device = selected

    selected_device = property(__get_selected_device, __set_selected_device)

    def get_possible_resolutions(self, devid):
        """
        Get the list of resolutions supported by the scanner

        Returns:
            An array of integer
        """
        self.__open_scanner(devid)
        possibles_resolutions = None
        for opt in self.__active_device[1].get_options():
            if opt[1] == "resolution":  # opt name
                possible_resolutions = opt[8]  # opt possible values
        if possible_resolutions == None:
            return []
        if type(possible_resolutions) == tuple:
            start = possible_resolutions[0] - (possible_resolutions[0] % 100)
            if start != possible_resolutions[0]:
                start += 100
            end = possible_resolutions[1] + 1
            possible_resolutions = [res for res in range(start, end, 100)]

        if not self.RECOMMENDED_RESOLUTION in possible_resolutions:
            possible_resolutions.append(self.RECOMMENDED_RESOLUTION)
        possible_resolutions.sort()
        return possible_resolutions

    def __open_scanner(self, devid):
        """
        Look for the selected scanner.

        Returns:
            Returns the corresponding sane device. None if no scanner has been
            found.
        """
        if not devid:
            if self.__active_device:
                self.__active_device[1].close()
            self.__active_device = None
            raise PaperworkScannerException("No scanner selected")

        if self.__active_device and devid == self.__active_device[0]:
            # already opened
            return

        if self.__active_device:
            self.__active_device[1].close()
            self.__active_device = None

        while self.__active_device == None:
            for device in self.available_devices:
                if device[0] == devid:
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
        """
        Apply the scanner settings to the currently opened device.
        """
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
        self.__open_scanner(self.__selected_device)
        self.__set_scanner_settings()
        return self.__active_device[1].scan()

    def close(self):
        """
        Make sure that any opened device is closed.
        """
        if self.__active_device != None:
            self.__active_device[1].close()
            self.__active_device = None
