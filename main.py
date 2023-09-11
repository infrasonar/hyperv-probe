from libprobe.probe import Probe
from lib.check.hyperv import check_hyperv
from lib.version import __version__ as version


if __name__ == '__main__':
    checks = {
        'hyperv': check_hyperv
    }

    probe = Probe("hyperv", version, checks)

    probe.start()
