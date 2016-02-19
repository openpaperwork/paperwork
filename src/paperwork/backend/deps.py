import sys

try:
    # suppress warnings from GI
    import gi
    gi.require_version('Poppler', '0.18')
    gi.require_version('PangoCairo', '1.0')
except:
    pass


MODULES = [
    (
        'Python GObject Introspection', 'gi',
        {
            'debian': 'python-gi',
            'fedora': 'pygobject3',
            'gentoo': 'dev-python/pygobject',
            'linuxmint': 'python-gi',
            'ubuntu': 'python-gi',
            'suse': 'python-gobject',
        },
    ),

    # TODO(Jflesch): check for jpeg support in PIL

    (
        'Poppler', 'gi.repository.Poppler',
        {
            'debian': 'gir1.2-poppler-0.18',
            'fedora': 'poppler-glib',
            'gentoo': 'app-text/poppler',
            'linuxmint': 'gir1.2-poppler-0.18',
            'ubuntu': 'gir1.2-poppler-0.18',
            'suse': 'typelib-1_0-Poppler-0_18',
        },
    ),

    (
        'Cairo', 'cairo',
        {
            'debian': 'python-gi-cairo',
            'fedora': 'pycairo',
            'gentoo': 'dev-python/pycairo',
            'linuxmint': 'python-gi-cairo',
            'ubuntu': 'python-gi-cairo',
            'suse': 'python-cairo',
        },
    ),
]


def check_python_version():
    python_ver = [str(x) for x in sys.version_info]
    if python_ver[0] != "2" or python_ver[1] != "7":
        raise Exception(
            "Expected python 2.7 ! Got python {}".format(".".join(python_ver))
        )
    return []


def find_missing_modules():
    """
    look for dependency that setuptools cannot check or that are too painful to
    install with setuptools
    """
    missing_modules = []

    for module in MODULES:
        try:
            __import__(module[1])
        except ImportError:
            missing_modules.append(module)
    return missing_modules


def find_missing_dependencies():
    missing = []
    missing += check_python_version()
    missing += find_missing_modules()
    return missing
