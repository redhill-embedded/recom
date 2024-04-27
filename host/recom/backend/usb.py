import enum

import usb1

from recom.backend.backend import RecomBackend

_usb_ctx = None

def _find_usb_devices(vid=None, pid=None, find_all=False):
    global _usb_ctx
    dev_list = []
    if _usb_ctx is None:
        _usb_ctx = usb1.USBContext()
        _usb_ctx.open()
    for dev in _usb_ctx.getDeviceList():
        dev_match = None
        if vid and pid:
            if dev.getVendorID() == vid and dev.getProductID() == pid:
                dev_match = dev
        elif vid:
            if dev.getVendorID() == vid:
                dev_match = dev
        elif pid:
            if dev.getProductID() == pid:
                dev_match = dev
        if dev_match:
            if find_all:
                # Add all found devices to list
                dev_list.append(USBDevice(dev_match))
            else:
                # Return first match
                return USBDevice(dev_match)
    return dev_list

def find_device_by_id(vid_pid):
    if isinstance(vid_pid, tuple):
        vid = vid_pid[0]
        pid = vid_pid[1]
    elif isinstance(vid_pid, str):
        if ':' in vid_pid:
            vp_parts = vid_pid.split(':', 1)
            vid = int(vp_parts[0].strip(), 16) if len(vp_parts[0]) else None
            pid = int(vp_parts[1].strip(), 16) if len(vp_parts[1]) else None
        else:
            vid = int(vid_pid.strip(), 16)
            pid = None
    if vid is not None and pid is not None:
        return _find_usb_devices(find_all=True, vid=vid, pid=pid)
    elif vid is not None:
        return _find_usb_devices(find_all=True, vid=vid)
    elif pid is not None:
        return _find_usb_devices(find_all=True, pid=pid)
    return None

def find_device_by_serial(serial):
    global _usb_ctx
    if _usb_ctx is None:
        _usb_ctx = usb1.USBContext()
        _usb_ctx.open()
    for device in _usb_ctx.getDeviceIterator(skip_on_error=True):
        if device.getSerialNumber() == serial:
            return device

def device_is_hub(device):
    # Check if the device class code is 0x09 (Hub) and subclass code is 0x00
    return device.getDeviceClass() == 0x09 and device.getDeviceSubClass() == 0x00


def get_all_usb_devices():
    global _usb_ctx
    if _usb_ctx is None:
        _usb_ctx = usb1.USBContext()
        _usb_ctx.open()
    dev_list = []
    for dev in _usb_ctx.getDeviceList():
        if not device_is_hub(dev):
            dev_list.append(USBDevice(dev))
    return dev_list

class CTRL_REQ(enum.IntEnum):
    DEVICE_VENDOR_OUT = 0x40
    DEVICE_VENDOR_IN = 0xC0
    INTERFACE_VENDOR_OUT = 0x41
    INTERFACE_VENDOR_IN = 0xC1


class USBDevice(RecomBackend):

    CLASS_VENDOR = 255

    def __init__(self, device_handle):
        self.handle = device_handle
        self.dev = None
        self.interfaces = []

    def __repr__(self):
        return "USB Device 0x%04X:0x%04X" % (self.handle.getVendorID(), self.handle.getProductID())

    @property
    def type(self):
        return "usb"

    @classmethod
    def find(cls, **kwargs) -> list:
        """Returns a list of all USB devices matching the provided constraings.

        If no constraints are provided, all USB devices will be returned.
        """
        if "id" in kwargs:
            return find_device_by_id(kwargs["id"])
        elif "serial" in kwargs:
            return find_device_by_serial(kwargs["serial"])
        else:
            return get_all_usb_devices()

    def open(self):
        self.dev = self.handle.open()

        # Find all interfaces
        for config in self.handle.iterConfigurations():
            for interface in config.iterInterfaces():
                for setting in interface.iterSettings():
                    if setting.getClass() == self.CLASS_VENDOR:
                        self.interfaces.append(USBInterface(self.dev, setting))

    def close(self):
        if self.dev:
            self.dev.close()

    def read(self, request, value=0, index=0, dataLen=512, timeout=1000):
        return self.dev.controlRead(CTRL_REQ.DEVICE_VENDOR_IN, request, value, index, dataLen, timeout)

    def write(self, request, data=b'', value=0, index=0, timeout=1000):
        return self.dev.controlWrite(CTRL_REQ.DEVICE_VENDOR_OUT, request, value, index, data, timeout)

    def get_interface_list(self):
        itf_list = []
        for itf in self.interfaces:
            itf_list.append([itf.itf_class, itf.itf_subclass,
                             itf.itf_protocol, itf.itf_str])
        return itf_list

    def get_interface(self, itf_identifier):
        if isinstance(itf_identifier, int):
            # Interface index
            return self.interfaces[itf_identifier]
        elif isinstance(itf_identifier, tuple):
            # Interface subclass/protocol tuple
            for itf in self.interfaces:
                if itf.itf_subclass == itf_identifier[0] and \
                   itf.itf_protocol == itf_identifier[1]:
                    return itf
        elif isinstance(itf_identifier, str):
            # Interface description string
            for itf in self.interfaces:
                if itf_identifier in itf.itf_str:
                    return itf
        return None


class USBInterface():

    EP_ATTR_CONTROL = 0
    EP_ATTR_ISO = 1
    EP_ATTR_BULK = 2
    EP_ATTR_INT = 3

    def __init__(self, dev_handle, itf_setting):
        self.dev = dev_handle
        self.itf = itf_setting
        self.itf_idx = itf_setting.getNumber()
        self.itf_class = self.itf.getClass()
        self.itf_subclass = self.itf.getSubClass()
        self.itf_protocol = self.itf.getProtocol()
        (lang_id, ) = self.dev.getSupportedLanguageList()
        str_desc_idx = itf_setting.getDescriptor()
        self.itf_str = self.dev.getStringDescriptor(str_desc_idx, lang_id)

        self.ep_out, self.ep_in = sorted(ep.getAddress() for ep in self.itf.iterEndpoints())


    def __repr__(self):
        return "%s: Subclass=%d, Protocol=%d, EP_OUT=0x%02X, EP_IN=0x%02X" % \
                    (self.itf_str, self.itf_subclass, self.itf_protocol,
                     self.ep_out, self.ep_in)

    @property
    def itf_string(self):
        return self.itf_str

    def controlRead(self, request, value=0, index=0, dataLen=512, timeout=1000):
        return self.dev.controlRead(CTRL_REQ.INTERFACE_VENDOR_IN, request, value, index, dataLen, timeout)

    def controlWrite(self, request, data=b'', value=0, index=0, timeout=1000):
        return self.dev.controlWrite(CTRL_REQ.INTERFACE_VENDOR_OUT, request, value, index, data, timeout)

    def read(self, dataLen=64, timeout=1000):
        return self.dev.bulkRead(self.ep_in, dataLen, timeout)

    def write(self, data, timeout=1000):
        return self.dev.bulkWrite(self.ep_out, data, timeout)
