"""
Paperwork configuration management code
"""

import ConfigParser
import os
from scanner import PaperworkScanner

class PaperworkConfig(object):
    """
    Paperwork config. See each accessor to know for what purpose each value is
    used.
    """

    # Possible config files are evaluated in the order they are in the array.
    # The last one of the list is the default one.
    CONFIGFILES = [
        "./paperwork.conf",
        os.path.expanduser("~/.paperwork.conf")
    ]

    def __init__(self):
        # values are stored directly in self.__configparser
        self.__configparser = ConfigParser.SafeConfigParser()

        configfile_found = False
        for self.__configfile in self.CONFIGFILES:
            if os.access(self.__configfile, os.R_OK):
                configfile_found = True
                print "Config file found: %s" % self.__configfile
                break
        if not configfile_found:
            print "Config file not found. Will use '%s'" % self.__configfile

    def read(self):
        """
        (Re)read the configuration.

        Beware that the current work directory may affect this operation:
        If there is a 'paperwork.conf' in the current directory, it will be
        read instead of '~/.paperwork.conf' ; see Paperwork.CONFIGFILES)
        """
        # smash the previous config
        self.__configparser = ConfigParser.SafeConfigParser()
        self.__configparser.read([self.__configfile])

        # make sure that all the sections exist
        if not self.__configparser.has_section("Global"):
            self.__configparser.add_section("Global")
        if not self.__configparser.has_section("OCR"):
            self.__configparser.add_section("OCR")
        if not self.__configparser.has_section("Scanner"):
            self.__configparser.add_section("Scanner")

    def __get_workdir(self):
        """
        Directory in which Paperwork must look for documents.
        Reminder: Documents are directories containing files called
        'paper.<X>.jpg', 'paper.<X>.txt' and possibly 'paper.<X>.box' ('<X>'
        being the page number).

        Returns:
            String.
        """
        try:
            return self.__configparser.get("Global", "WorkDirectory")
        except ConfigParser.NoOptionError:
            return os.path.expanduser("~/papers")

    def __set_workdir(self, work_dir_str):
        """
        Set the work directory.
        """
        self.__configparser.set("Global", "WorkDirectory", work_dir_str)

    workdir = property(__get_workdir, __set_workdir)

    def __get_ocrlang(self):
        """
        OCR lang. This the lang specified to Tesseract when doing OCR. The
        string here in the configuration is identical to the one passed to
        tesseract on the command line.

        String.
        """
        try:
            return self.__configparser.get("OCR", "Lang")
        except ConfigParser.NoOptionError:
            return "eng"

    def __set_ocrlang(self, lang):
        """
        Set the OCR lang
        """
        self.__configparser.set("OCR", "Lang", lang)

    ocrlang = property(__get_ocrlang, __set_ocrlang)

    def __get_scanner_devid(self):
        """
        This is the id of the device selected by the user.

        String.
        """
        try:
            return self.__configparser.get("Scanner", "Device")
        except ConfigParser.NoOptionError:
            return None

    def __set_scanner_devid(self, devid):
        """
        Set the device id selected by the user to use for scanning
        """
        self.__configparser.set("Scanner", "Device", devid)

    scanner_devid = property(__get_scanner_devid, __set_scanner_devid)

    def __get_scanner_resolution(self):
        """
        This is the resolution of the scannner used for normal scans.

        String.
        """
        try:
            return int(self.__configparser.get("Scanner", "Resolution"))
        except ConfigParser.NoOptionError:
            return PaperworkScanner.RECOMMENDED_RESOLUTION

    def __set_scanner_resolution(self, resolution):
        """
        Set the scanner resolution used for normal scans.
        """
        self.__configparser.set("Scanner", "Resolution", str(resolution))

    scanner_resolution = property(__get_scanner_resolution,
                                  __set_scanner_resolution)

    def write(self):
        """
        Rewrite the configuration file. It rewrites the same file than
        PaperworkConfig.read() read.
        """
        file_path = self.__configfile
        print "Writing %s ... " % file_path
        with open(file_path, 'wb') as file_descriptor:
            self.__configparser.write(file_descriptor)
        print "Done"
