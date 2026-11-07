from dataclasses import dataclass
from typing import Optional


@dataclass
class RecomDeviceDescriptor:
    type: str
    dev_id: tuple
    dev_path: tuple


@dataclass
class DeviceIdentity:
    """What a backend needs to find the same physical device again after it
    reboots (e.g. after a firmware update).

    ``location`` is where it is attached (backend-specific, e.g. USB bus and
    port chain); ``serial`` its serial number, if known, so it can also be
    found if it comes back somewhere else; ``instance`` a value that changes
    whenever the device re-attaches (e.g. the USB device address), so a
    reboot is recognised even if the disconnect itself was too quick to
    observe."""
    type: str
    dev_id: tuple
    location: tuple
    serial: Optional[str] = None
    instance: Optional[int] = None


class RecomBackend:

    def __init__(self):
        pass    

    @classmethod
    def type(self):
        raise NotImplementedError
    
    @classmethod
    def find(cls, **kwargs) -> list:
        return []
    
    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def get_interfacelist(self):
        raise NotImplementedError
    
    def get_interface(self):
        raise NotImplementedError

    def read(self):
        raise NotImplementedError
    
    def write(self):
        raise NotImplementedError

    def get_device_path(self):
        """Returns a backend-specific device path that is unique for this device"""
        raise NotImplementedError

    def get_identity(self) -> DeviceIdentity:
        """Returns what is needed to find this device again after a reboot."""
        raise NotImplementedError

    @classmethod
    def wait_for_disconnect(cls, identity: DeviceIdentity, timeout: float) -> bool:
        """Waits until the device described by ``identity`` has gone away (or
        has already re-attached). Returns False on timeout."""
        raise NotImplementedError

    @classmethod
    def wait_for_reconnect(cls, identity: DeviceIdentity,
                           timeout: float) -> Optional[RecomDeviceDescriptor]:
        """Waits until the device described by ``identity`` is back and can be
        opened; returns its descriptor, or None on timeout."""
        raise NotImplementedError
