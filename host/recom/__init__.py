import pkg_resources

from recom.device import RecomDevice, RecomDeviceException
from recom.interface import RecomInterface
from recom import log

__version__ = pkg_resources.get_distribution("recom").version

__all__ = ["RecomDevice", "RecomInterface", "RecomDeviceException", "log"]
