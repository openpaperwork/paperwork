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
            'debian': 'python3-gi',
            'fedora': 'pygobject3',
            'gentoo': 'dev-python/pygobject',  # Python 3 ?
            'linuxmint': 'python3-gi',
            'ubuntu': 'python3-gi',
            'suse': 'python-gobject',  # Python 3 ?
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
            'debian': 'python3-gi-cairo',
            'fedora': 'pycairo',  # Python 3 ?
            'gentoo': 'dev-python/pycairo',  # Python 3 ?
            'linuxmint': 'python-gi-cairo',  # Python 3 ?
            'ubuntu': 'python3-gi-cairo',
            'suse': 'python-cairo',  # Python 3 ?
        },
    ),
]


def check_python_version():
    python_ver = (sys.version_info[0], sys.version_info[1])
    if python_ver < (3, 0):
        raise Exception(
            "Expected python >= 3.0 !"
            "Got python {}".format(".".join(python_ver))
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
