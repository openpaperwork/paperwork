"""
Code relative to scanner management.
"""

import gettext
import gtk
import pyocr.pyocr
import sys
import time
try:
    import sane
    HAS_SANE = True
except ImportError, exce:
    print "Sane support disabled, because of: %s" % (exce)
    HAS_SANE = False

_ = gettext.gettext
_opened_scanner_instances = 0


class PaperworkScannerException(Exception):
    """
    Exception raised in case we try to use an invalid scanner configuration
    """
    def __init__(self, message):
        Exception.__init__(self, message)


def sane_init():
    """
    Initialize Sane.

    Warning:
        Apparently, it can and must be only run from the main thread
    """
    global _opened_scanner_instances

    if not HAS_SANE:
        raise PaperworkScannerException("Sane module not found")

    if _opened_scanner_instances == 0:
        print "Initializing sane module"
        sys.stdout.flush()
        sane.init()
    _opened_scanner_instances += 1


def sane_exit():
    """
    Cleanup Sane.

    Warning:
        Apparently, it can and must be only run from the main thread
    """
    global _opened_scanner_instances

    _opened_scanner_instances -= 1
    if _opened_scanner_instances == 0:
        print "Cleaning sane module"
        sys.stdout.flush()
        sane.exit()


def assert_sane_init():
    """
    Make sure that sane has been initialized
    """
    global _opened_scanner_instances
    assert(_opened_scanner_instances > 0)


class PaperworkPhyScanSrc(object):
    def __init__(self, paperwork_dev, sane_dev_id):
        self.__sane_dev_id = sane_dev_id
        self.paperwork_dev = paperwork_dev
        self._sane_dev_obj = self.__open_scanner(sane_dev_id)

    @staticmethod
    def __open_scanner(dev_id):
        sane_init()

        while True:
            try:
                return sane.open(dev_id)
            except RuntimeError:
                # the sane module doesn't return any specific exception :(
                msg = _("No scanner found (is your scanner turned on ?)."
                       " Look again ?")
                # TODO(Jflesch): This should be in the controller/view code
                dialog = gtk.MessageDialog(flags=gtk.DIALOG_MODAL,
                                           type=gtk.MESSAGE_WARNING,
                                           buttons=gtk.BUTTONS_YES_NO,
                                           message_format=msg)
                response = dialog.run()
                dialog.destroy()
                if response == gtk.RESPONSE_NO:
                    raise PaperworkScannerException("No scanner found")

    def _set_scanner_settings(self, batch=False, source=None):
        """
        Apply the scanner settings to the currently opened device.
        """
        if source == None:
            source = self.paperwork_dev.SCANNER_SOURCE_AUTO
        try:
            self._sane_dev_obj.resolution = \
                    self.paperwork_dev.selected_resolution
        except AttributeError, exc:
            print "WARNING: Can't set scanner resolution: " + str(exc)
        try:
            self._sane_dev_obj.source = source
        except AttributeError, exc:
            print "WARNING: Can't set scanner source: " + str(exc)
        except sane.error, exc:
            print "WARNING: Can't set scanner source: " + str(exc)
        try:
            self._sane_dev_obj.mode = 'Color'
        except AttributeError, exc:
            print "WARNING: Can't set scanner mode: " + str(exc)
        try:
            self._sane_dev_obj.batch_scan = batch
        except AttributeError, exc:
            print "WARNING: Can't set batch_scan mode: " + str(exc)

    def __get_possible_resolutions(self):
        res = []
        for opt in self._sane_dev_obj.get_options():
            if opt[1] == "resolution":  # opt name
                res = opt[8]  # opt possible values
                break
        if type(res) == tuple:
            start = (res[0] - (res[0] % 100))
            if start != res[0]:
                start += 100
                end = res[1] + 1
                res = [r for r in range(start, end, 100)]
        else:
            res = res[:]

        if not self.paperwork_dev.RECOMMENDED_RESOLUTION in res:
            res.append(self.paperwork_dev.RECOMMENDED_RESOLUTION)
        res.sort()
        return res

    possible_resolutions = property(__get_possible_resolutions)

    def __get_possible_sources(self):
        sources = []
        for opt in self._sane_dev_obj.get_options():
            if opt[1] == "source":  # opt name
                sources = opt[8]  # opt possible values
                break
        return sources

    possible_sources = property(__get_possible_sources)

    @staticmethod
    def scan():
        raise Exception("Must be overloaded")

    def close(self):
        self._sane_dev_obj.close()
        sane_exit()

    def __str__(self):
        return self.__sane_dev_id


class PaperworkSingleScan(PaperworkPhyScanSrc):
    def __init__(self, paperwork_dev, sane_dev_id):
        PaperworkPhyScanSrc.__init__(self, paperwork_dev, sane_dev_id)
        self._set_scanner_settings(batch=False,
                                   source=PaperworkScanner.SCANNER_SOURCE_AUTO)

    def scan(self):
        return self._sane_dev_obj.scan()


class PaperworkMultiScan(PaperworkPhyScanSrc):
    def __init__(self, paperwork_dev, sane_dev_id):
        PaperworkPhyScanSrc.__init__(self, paperwork_dev, sane_dev_id)
        self._set_scanner_settings(batch=True,
                                   source=PaperworkScanner.SCANNER_SOURCE_ADF)
        self.__scan_iter = self._sane_dev_obj.multi_scan()

    def scan(self):
        return self.__scan_iter.next()

    def close(self):
        del(self.__scan_iter)
        PaperworkPhyScanSrc.close(self)


class PaperworkScanner(object):
    """
    Handle a scanner. Please note that the scanner init is done in a
    lazy way: We only look for the scanner when the user request a scan.
    """

    RECOMMENDED_RESOLUTION = 300
    CALIBRATION_RESOLUTION = 200

    SCANNER_SOURCE_AUTO = "Auto"
    SCANNER_SOURCE_FLATBED = "Flatbed"
    SCANNER_SOURCE_ADF = "ADF" # automatic document feeder

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

        devs = []
        sane_init()
        try:
            devs = sane.get_devices()
            print "-- Devices found:"
            for dev in devs:
                print dev
            print "--"
        finally:
            sane_exit()
        return devs

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
        elif len(pyocr.pyocr.get_available_tools()) <= 0:
            self.state = (False,
                          _('No OCR tool found not available. Can\'t do OCR'))
        elif not selected:
            self.state = (False, _('No scanner has been selected'))
        else:
            self.state = (True, _('Scan'))
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

        device = self.open(dev_id=devid)
        try:
            res = device.possible_resolutions
        finally:
            device.close()
        return res

    def get_possible_sources(self, devid):
        if not HAS_SANE:
            return []

        device = self.open(dev_id=devid)
        try:
            sources = device.possible_sources
        finally:
            device.close()
        return sources

    def load_settings_from_config(self, config):
        self.selected_device = config.scanner_devid
        self.selected_resolution = config.scanner_resolution

    def open(self, multiscan=False, dev_id=None):
        if not HAS_SANE:
            raise PaperworkScannerException("Sane module not found")
        if dev_id == None:
            dev_id = self.__selected_device
        if dev_id == None:
            raise PaperworkScannerException("No scanner selected")
        if not multiscan:
            return PaperworkSingleScan(self, dev_id)
        else:
            return PaperworkMultiScan(self, dev_id)

