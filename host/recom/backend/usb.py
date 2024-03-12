import enum
import usb.core
import usb.util

def find_usb_device_by_vid_pid(vid_pid):
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
        return list(usb.core.find(find_all=True, idVendor=vid, idProduct=pid))
    elif vid is not None:
        return list(usb.core.find(find_all=True, idVendor=vid))
    elif pid is not None:
        return list(usb.core.find(find_all=True, idProduct=pid))
    return None

def find_usb_device_by_serial(serial):
    return usb.core.find(serial=serial)

class CTRL_REQ(enum.IntEnum):
    DEVICE_VENDOR_OUT = 0x40
    DEVICE_VENDOR_IN = 0xC0
    INTERFACE_VENDOR_OUT = 0x41
    INTERFACE_VENDOR_IN = 0xC1


class USBDevice:

    def __init__(self, dev_handle):
        self.dev = dev_handle
        self.interfaces = []

        for cfg in self.dev:
            for itf in cfg:
                self.interfaces.append(USBInterface(self.dev, itf))
        self.dev.set_configuration(1)

    def __repr__(self):
        return "USB Device 0x%04X:0x%04X" % (self.dev.idVendor, self.dev.idProduct)

    @property
    def dev_type(self):
        return 'usb'

    def controlRead(self, request, value=0, index=0, dataLen=512, timeout=1000):
        return self.dev.ctrl_transfer(CTRL_REQ.DEVICE_VENDOR_IN, request, value, index, dataLen, timeout)

    def controlWrite(self, request, data=b'', value=0, index=0, timeout=1000):
        return self.dev.ctrl_transfer(CTRL_REQ.DEVICE_VENDOR_OUT, request, value, index, data, timeout)

    def get_interface_list(self):
        itf_list = []
        for itf in self.interfaces:
            itf_list.append([itf.desc.bInterfaceClass, itf.desc.bInterfaceSubClass,
                             itf.desc.bInterfaceProtocol, itf.itf_str])
        return itf_list

    def get_interface(self, itf_identifier):
        if isinstance(itf_identifier, int):
            # Interface index
            return self.interfaces[itf_identifier]
        elif isinstance(itf_identifier, tuple):
            # Interface subclass/protocol tuple
            for itf in self.interfaces:
                if itf.desc.bInterfaceSubClass == itf_identifier[0] and \
                   itf.desc.bInterfaceProtocol == itf_identifier[1]:
                    return itf
        elif isinstance(itf_identifier, str):
            # Interface description string
            for itf in self.interfaces:
                if itf_identifier in itf.itf_str:
                    return itf
        return None


class USBInterface():

    def __init__(self, dev_handle, itf_desc):
        self.dev = dev_handle
        self.desc = itf_desc
        self.itf_idx = itf_desc.bInterfaceNumber
        interface = usb.core.Interface(self.dev, self.itf_idx)
        self.eps = []
        self.ep_in = usb.util.find_descriptor(interface, custom_match = lambda e: \
                                            usb.util.endpoint_direction(e.bEndpointAddress) == \
                                            usb.util.ENDPOINT_IN)
        self.ep_out = usb.util.find_descriptor(interface, custom_match = lambda e: \
                                            usb.util.endpoint_direction(e.bEndpointAddress) == \
                                            usb.util.ENDPOINT_OUT)
        self.subclass = self.desc.bInterfaceSubClass
        self.protocol = self.desc.bInterfaceProtocol
        self.itf_str = usb.util.get_string(self.dev, self.desc.iInterface)

    def __repr__(self):
        return "%s: Subclass=%d, Protocol=%d, EP_OUT=0x%02X, EP_IN=0x%02X" % \
                    (self.itf_str, self.subclass, self.protocol, self.ep_out.bEndpointAddress,
                                                                 self.ep_in.bEndpointAddress)

    @property
    def itf_string(self):
        return self.itf_str

    def controlRead(self, request, value=0, index=0, dataLen=512, timeout=1000):
        return self.dev.ctrl_transfer(CTRL_REQ.INTERFACE_VENDOR_IN, request, value, index, dataLen, timeout)

    def controlWrite(self, request, data=b'', value=0, index=0, timeout=1000):
        return self.dev.ctrl_transfer(CTRL_REQ.INTERFACE_VENDOR_OUT, request, value, index, data, timeout)

    def read(self, dataLen=64, timeout=1000):
        return self.ep_in.read(dataLen, timeout)

    def write(self, data, timeout=1000):
        return self.ep_out.write(data, timeout)
