#from interface import DeviceInterface
import enum
import struct
from recom.backend.usb import find_device_by_serial, find_device_by_id
#from recom.backend.uart import find_device_by_serial, find_device_by_id
from recom.backend.usb import USBDevice
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

class RecomDeviceException(Exception):
    pass
class BaseDevice:

    def __init__(self, device):
        self._interfaces = []
        self._comsBackend = None
        self.dev = device
        #print(self.dev)

        # TODO: Detect and setup COMs backend
        # For now, default to USB
        self._comsBackend = USBDevice(device)

    def __repr__(self):
        return repr(self._comsBackend)

    def _detectInterfaces(self):
        #If USB, get the interfaces from the USB library/descriptor
        #If UART or other interface, use the control interface to query the available interfaces
        pass

    def getAllInterfaces(self):
        """Returns a list of available interfaces"""
        return self._comsBackend.get_interface_list()

    def getRecomDevID(self):
        data = self._comsBackend.controlRead(BASE_DEV_CMDS.CMD_RECOM_DEV_ID)
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
            raise RecomDeviceException("Interface not found")
        return RecomInterface(self, itf)

    def getInterfaceHandleFromNumber(self, itf_num):
        """Finds an interface based on its number in the interface list and returns its handle"""
        itf_list = self._comsBackend.get_interface_list()
        if itf_num >= len(itf_list):
            raise RecomDeviceException("Interface number out of range")
        itf = self._comsBackend.get_interface(itf_list[itf_num])
        return RecomInterface(self, itf)

    def getHwID(self):
        # The HW ID is a 32-bit number
        data = self._comsBackend.controlRead(BASE_DEV_CMDS.CMD_HW_ID)
        return struct.unpack('<I', data)

    def getHwRev(self):
        # The HW revision is a 32-bit number
        data = self._comsBackend.controlRead(BASE_DEV_CMDS.CMD_HW_REV)
        return struct.unpack('<I', data)

    def getFwRev(self):
        # The FW revision is a string
        data = self._comsBackend.controlRead(BASE_DEV_CMDS.CMD_FW_REV)
        return ''.join(chr(x) for x in data)

    def getSerial(self):
        # The device serial number is a string
        data = self._comsBackend.controlRead(BASE_DEV_CMDS.CMD_SERIAL)
        return ''.join(chr(x) for x in data)

class RecomDevice(BaseDevice):

    def __init__(self, serial=None, device_id=None, dev_handle=None):
        if dev_handle:
            dev = dev_handle
        else:
            dev = self._find_device(serial, device_id)
            if dev is None:
                raise RecomDeviceException("No device found")
        super().__init__(dev)
        recom_dev_info = self.getRecomDevID()
        if recom_dev_info is None:
            raise RecomDeviceException("Device is not a recom device - Invalid ID response")
        elif recom_dev_info["id"] != RECOM_DEV_ID:
            raise RecomDeviceException("Device is not a recom device - ID mismatch")
        self.protocol_version = recom_dev_info["protocol_version"]
        self.recom_fw_version = recom_dev_info["version_string"]


    def _find_device(self, serial, device_id):
        if serial is not None:
            # Check if we have a USB device with the specified serial
            dev = find_device_by_serial(serial)
            if dev is not None:
                return dev
            # Next, check if there is a serial device with the specified serial
            #dev = find_serial_device_by_serial(serial)
            return dev
        elif device_id is not None:
            # Check if we can find a USB device with the specified device_id (VID:PID in this case)
            dev = find_device_by_id(device_id)
            if dev is not None:
                if len(dev) > 1:
                    raise RecomDeviceException("More than one device found!")
                elif len(dev) == 1:
                    return dev[0]
            # No USB devices found, now try to find serial devices with the specified device_id (port ID)
            #dev = find_serial_device_by_com_port(device_id)
            return dev


    def reset(self):
        pass

    @property
    def hw_id(self):
        return self.getHwID()[0]

    @property
    def hw_revision(self):
        return self.getHwRev()[0]

    @property
    def fw_revision(self):
        return self.getFwRev()

    @property
    def serial(self):
        return self.getSerial()


