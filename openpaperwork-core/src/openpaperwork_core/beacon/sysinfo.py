import os
import multiprocessing
import platform
import psutil
import sys

try:
    import distro
except (ImportError, ValueError):
    assert os.name == "nt"

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    @classmethod
    def get_interfaces(cls):
        return ['stats']

    def stats_get(self, out: dict):
        if os.name == 'nt':
            distribution = str(platform.win32_ver())
        else:
            distribution = str((
                distro.id(),
                distro.version(),
                distro.name()
            ))
        processor = ""
        os_name = os.name
        if os_name != 'nt':  # processor contains too much infos on Windows
            processor = str(platform.processor())

        cpu_freq = None
        if hasattr(psutil, 'cpu_freq'):
            cpu_freq = psutil.cpu_freq()
        if cpu_freq is not None:
            cpu_freq = int(cpu_freq.max)

        if cpu_freq is not None:
            out['cpu_freq'] = cpu_freq
        out['cpu_count'] = multiprocessing.cpu_count()
        out['os_name'] = os_name
        out['platform_architecture'] = str(platform.architecture())
        out['platform_distribution'] = distribution
        out['platform_machine'] = platform.machine()
        out['platform_mem'] = int(psutil.virtual_memory().total)
        out['platform_processor'] = processor
        out['software_python'] = sys.version
        out['software_release'] = platform.release()
        out['software_system'] = platform.system()
        return out
