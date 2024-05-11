import serial
import serial.tools.list_ports


from recom.backend.backend import RecomBackend


class SerialDevice(RecomBackend):

    def __init__(self):
        pass

    @property
    def type(self):
        return "uart"

    @classmethod
    def find(cls, **kwargs) -> list:
        return []

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
