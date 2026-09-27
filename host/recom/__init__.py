from importlib.metadata import PackageNotFoundError, version

from recom.device import RecomDevice, RecomDeviceException
from recom.interface import RecomInterface
from recom import log

# importlib.metadata, not pkg_resources: current setuptools no longer ships
# pkg_resources, and fresh Python 3.12+ environments have no setuptools at
# all -- `import recom` would fail there.
try:
    __version__ = version("recom")
except PackageNotFoundError:    # running from a source tree without installing
    __version__ = "unknown"

__all__ = ["RecomDevice", "RecomInterface", "RecomDeviceException", "log"]
