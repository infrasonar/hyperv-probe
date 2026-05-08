from libprobe.probe import Probe
from lib.check.hyperv import CheckHyperV
from lib.version import __version__ as version


if __name__ == '__main__':
    checks = (
        CheckHyperV,
    )

    probe = Probe("hyperv", version, checks, loggers=('aiowmi',))

    probe.start()
