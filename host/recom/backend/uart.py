import serial
import serial.tools.list_ports


from recom.backend.backend import RecomBackend, RecomDeviceDescriptor


class SerialDevice(RecomBackend):

    def __init__(self, device_descriptor: RecomDeviceDescriptor):
        pass

    @classmethod
    def type(cls):
        return "uart"

    @classmethod
    def find(cls, **kwargs) -> list:
        return []

    def open(self):
        pass

    def close(self):
        pass

    def get_interfacelist(self):
        return []

    def get_interface(self):
        return None

    def read(self, request, value=0, index=0, dataLen=512, timeout=1000):
        return []

    def write(self, request, data=b'', value=0, index=0, timeout=1000):
        pass

    def get_device_path(self):
        """Returns a backend-specific device path that is unique for this device"""
        return []
