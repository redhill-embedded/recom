from dataclasses import dataclass


@dataclass
class RecomDeviceDescriptor:
    type: str
    dev_id: tuple
    dev_path: tuple


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
