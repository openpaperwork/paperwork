import ConfigParser
import os

class AppConfig(object):
    # possible config files are evaluated in the order they are in the array
    # last one of the list is the default one
    CONFIGFILES = [ "./paperwork.conf", "~/.paperwork.conf" ]

    def __init__(self):
        self.read()

    def read(self):
        self.configparser = ConfigParser.SafeConfigParser()
        configfile_found = False
        for self.configfile in self.CONFIGFILES:
            self.configfile = os.path.expanduser(self.configfile)
            if os.access(self.configfile, os.R_OK):
                configfile_found = True
                print "Config file found: %s" % self.configfile
                break
        if not configfile_found:
            print "Config file not found. Will use '%s'" % self.configfile

        self.configparser.read([ self.configfile ])

        if not self.configparser.has_section("Global"):
            self.configparser.add_section("Global")
        if not self.configparser.has_section("OCR"):
            self.configparser.add_section("OCR")

    @property
    def workdir(self):
        try:
            return self.configparser.get("Global", "WorkDirectory")
        except:
            return os.path.expanduser("~/papers")

    @workdir.setter
    def workdir(self, wd):
        self.configparser.set("Global", "WorkDirectory", wd)

    @property
    def ocrlang(self):
        try:
            return self.configparser.get("OCR", "Lang")
        except:
            return "eng"

    @ocrlang.setter
    def ocrlang(self, lang):
        self.configparser.set("OCR", "Lang", lang)

    def write(self):
        f = self.configfile
        print "Writing %s ... " % f
        with open(f, 'wb') as fd:
            self.configparser.write(fd)
        print "Done"

