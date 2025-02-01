import pkg_resources

from recom.device import RecomDevice, RecomDeviceException
from recom.interface import RecomInterface

__version__ = pkg_resources.get_distribution("recom").version

__all__ = ["RecomDevice", "RecomInterface", "RecomDeviceException"]
