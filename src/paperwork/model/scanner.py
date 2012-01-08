"""
Code relative to scanner management.
"""

import gettext
import gtk
import tesseract
try:
    import sane
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
        # selected_device: one value from sane.get_devices()[0]
        # (scanner id)
        self.__selected_device = None
        self.selected_resolution = self.RECOMMENDED_RESOLUTION

        # state = (X, Y):
        # X = True/False: True = sane is init and a scanner is selected
        #   ; False = cannot scan
        # Y = Scan action status (string)
        if not HAS_SANE:
            self.state = (False, _('Sane module not found'))
        else:
            self.state = (False, _("No scanner set"))

    def __get_available_devices(self):
        """
        Return the list of available scan devices (array)
        """
        if not HAS_SANE:
            return []

        sane.init()
        try:
            return sane.get_devices()
        finally:
            sane.exit()

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
        if not HAS_SANE:
            return []

        possibles_resolutions = []
        sane.init()
        try:
            device = self.__open_scanner(devid)

            try:
                for opt in device[1].get_options():
                    if opt[1] == "resolution":  # opt name
                        possible_resolutions = opt[8]  # opt possible values

                if type(possible_resolutions) == tuple:
                    start = (possible_resolutions[0]
                             - (possible_resolutions[0] % 100))
                    if start != possible_resolutions[0]:
                        start += 100
                    end = possible_resolutions[1] + 1
                    possible_resolutions = [res for res in range(start, end, 100)]

                if not self.RECOMMENDED_RESOLUTION in possible_resolutions:
                    possible_resolutions.append(self.RECOMMENDED_RESOLUTION)
                possible_resolutions.sort()
            finally:
                self.__close_scanner(device)
        finally:
            sane.exit()
        return possible_resolutions

    def __open_scanner(self, devid=None):
        """
        Look for the selected scanner.

        Returns:
            Returns the corresponding sane device. None if no scanner has been
            found.
        """
        if not HAS_SANE:
            raise Exception("Sane module not found")

        if devid == None:
            devid = self.__selected_device
        if devid == None:
            raise Exception("No scanner selected")

        while True:
            for device in sane.get_devices():
                if device[0] == devid:
                    print "Will use device '%s'" % (str(device))
                    dev_obj = sane.open(device[0])
                    return (device[0], dev_obj)

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

    def __close_scanner(self, device):
        device[1].close()

    def __set_scanner_settings(self, device):
        """
        Apply the scanner settings to the currently opened device.
        """
        try:
            device[1].resolution = self.selected_resolution
        except AttributeError, exc:
            print "WARNING: Can't set scanner resolution: " + exc
        try:
            device[1].mode = 'Color'
        except AttributeError, exc:
            print "WARNING: Can't set scanner mode: " + exc

    def scan(self):
        """
        Run a scan, and returns the corresponding output image.
        """
        if not HAS_SANE:
            raise Exception("Sane module not found")
        scan = None
        sane.init()
        try:
            device = self.__open_scanner()
            try:
                self.__set_scanner_settings(device)
                scan = device[1].scan()
            finally:
                self.__close_scanner(device)
        finally:
            sane.exit()
        return scan
