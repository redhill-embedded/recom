#from interface import DeviceInterface
import enum
import struct
from recom.backend import backends
from recom.backend.backend import RecomDeviceDescriptor
from recom.interface import RecomInterface

# Recom device identifier. DO NOT CHANGE!
RECOM_DEV_ID = 0x53C08A30

class BASE_DEV_CMDS(enum.IntEnum):
    CMD_RECOM_DEV_ID    = 0x00,
    CMD_HW_ID           = 0x01,
    CMD_HW_REV          = 0x02,
    CMD_FW_REV          = 0x03,
    CMD_SERIAL          = 0x04,
    CMD_RESET           = 0x05
    CMD_GET_INTERFACES  = 0x06,

class RESET(enum.IntEnum):
    RCM_DEV_RST_REBOOT      = 0x00,     # Reset the device back to the application
    RCM_DEV_RST_BOOTLOADER  = 0x01,     # Reset to bootloader
    RCM_DEV_RST_ROM_BOOT    = 0x02,     # Reset to built-in ROM bootloader

class RecomDeviceException(Exception):
    class NoDeviceFound(Exception):
        pass

    class MultipleDevicesFound(Exception):
        pass

    class InterfaceNotFound(Exception):
        pass

    class InterfaceNumOutOfRange(Exception):
        pass

    class NotARecomDevice(Exception):
        pass


class BaseDevice:

    _comsBackend = None

    def __init__(self, device_descriptor: RecomDeviceDescriptor):
        self._interfaces = []

        # Loop through all backends and see if one can find a device based on
        # the provided device descriptor
        for be in backends:
            if be.type() == device_descriptor.type:
                cbe = be(device_descriptor)
                if cbe is not None:
                    self._comsBackend = cbe
                    break
        if self._comsBackend is None:
            raise RecomDeviceException.NoDeviceFound()
        self._comsBackend.open()

    def __del__(self):
        if self._comsBackend:
            self._comsBackend.close()

    def __repr__(self):
        return repr(self._comsBackend)

    def getAllInterfaces(self):
        """Returns a list of available interfaces"""
        return self._comsBackend.get_interface_list()

    def getRecomDevID(self):
        data = self._comsBackend.read(BASE_DEV_CMDS.CMD_RECOM_DEV_ID, timeout=100)
        if len(data) <= 6:
            return None
        id, prot_ver = struct.unpack('<IH', data[0:6])
        ver_str = str(data[6:], 'utf-8')
        return {
            "id": id,
            "protocol_version": prot_ver,
            "version_string": ver_str,
        }

    def getInterfaceHandleFromID(self, itf_id):
        """Finds an interface based on its ID and returns its handle"""
        itf = self._comsBackend.get_interface(itf_id)
        if itf is None:
            raise RecomDeviceException.InterfaceNotFound
        return RecomInterface(self, itf)

    def getInterfaceHandleFromNumber(self, itf_num):
        """Finds an interface based on its number in the interface list and returns its handle"""
        itf_list = self._comsBackend.get_interface_list()
        if itf_num >= len(itf_list):
            raise RecomDeviceException.InterfaceNumOutOfRange
        itf = self._comsBackend.get_interface(itf_list[itf_num])
        return RecomInterface(self, itf)

    def getHwID(self):
        # The HW ID is a 32-bit number
        data = self._comsBackend.read(BASE_DEV_CMDS.CMD_HW_ID)
        return struct.unpack('<I', data)

    def getHwRev(self):
        # The HW revision is a 32-bit number
        data = self._comsBackend.read(BASE_DEV_CMDS.CMD_HW_REV)
        return struct.unpack('<I', data)

    def getFwRev(self):
        # The FW revision is a string
        data = self._comsBackend.read(BASE_DEV_CMDS.CMD_FW_REV)
        return ''.join(chr(x) for x in data)

    def getSerialString(self, index=0):
        # The serial number at index as a string
        data = self._comsBackend.read(BASE_DEV_CMDS.CMD_SERIAL, index=index)
        return ''.join(chr(x) for x in data)

    def getSerialBytes(self, index=0):
        # The serial number at index as a byte array
        return self._comsBackend.read(BASE_DEV_CMDS.CMD_SERIAL, index=index)

    def sendReset(self, reset: int):
        # Send a reset command
        data = struct.pack("B", reset)
        self._comsBackend.write(BASE_DEV_CMDS.CMD_RESET, data)

class RecomDevice(BaseDevice):

    def __init__(self, **kwargs):
        # We can initialize a RecomDevice with a known device handle, or we can provide device
        # constraints paramters that will be used to find the device automatically.
        if "device" not in kwargs:
            # No device handle/object provided. Try to find a device using the provided constraints
            dev = self._find_device(**kwargs)
            if dev is None:
                raise RecomDeviceException.NoDeviceFound
        else:
            # Device descriptor provided. Use it
            dev = kwargs["device"]
        super().__init__(dev)
        recom_dev_info = self.getRecomDevID()
        if recom_dev_info is None:
            raise RecomDeviceException.NotARecomDevice("Invalid ID response")
        elif recom_dev_info["id"] != RECOM_DEV_ID:
            raise RecomDeviceException.NotARecomDevice("ID mismatch")
        self.protocol_version = recom_dev_info["protocol_version"]
        self.recom_fw_version = recom_dev_info["version_string"]


    def _find_device(self, **kwargs):
        # Loop through the backends and let them do the work finding device(s) based on
        # the provided device constraints
        dev_list = []
        for be in backends:
            dev_list.extend(be.find(**kwargs))
        if dev_list == []:
            raise RecomDeviceException.NoDeviceFound
        if len(dev_list) > 1:
            print(dev_list)
            raise RecomDeviceException.MultipleDevicesFound
        return dev_list[0]

    def reset(self, reset: int):
        self.sendReset(reset)

    @property
    def hw_id(self):
        return self.getHwID()[0]

    @property
    def hw_revision(self):
        return self.getHwRev()[0]

    @property
    def fw_revision(self):
        return self.getFwRev()

    def get_serial(self, index=0, format="string"):
        if (format == "bytes"):
            return self.getSerialBytes(index=index)
        else:
            return self.getSerialString(index=index)

    @classmethod
    def scan(cls):
        pass

    @property
    def device_path(self):
        self._comsBackend.get_device_path()
