#from interface import DeviceInterface
import enum
import struct
from dataclasses import dataclass
from typing import Optional

from recom.backend import backends
from recom.backend.backend import RecomDeviceDescriptor
from recom.interface import RecomInterface
from recom.exceptions import RecomDeviceException
from recom.log import format_log
from recom.fw_image import ImageVersion

# Recom device identifier. DO NOT CHANGE!
RECOM_DEV_ID = 0x53C08A30

class BASE_DEV_CMDS(enum.IntEnum):
    CMD_RECOM_DEV_ID    = 0x00,
    CMD_HW_ID           = 0x01,
    CMD_HW_REV          = 0x02,
    CMD_FW_REV          = 0x03,
    CMD_SERIAL          = 0x04,
    CMD_RESET           = 0x05,
    CMD_GET_INTERFACES  = 0x06,
    CMD_LOG_READ        = 0x07,
    # Firmware update (protocol version 2+)
    CMD_FW_INFO         = 0x08,
    CMD_FW_BEGIN        = 0x09,
    CMD_FW_DATA         = 0x0A,
    CMD_FW_FINISH       = 0x0B,
    CMD_FW_APPLY        = 0x0C,
    CMD_FW_ABORT        = 0x0D,
    CMD_FW_STATUS       = 0x0E,
    CMD_FW_IMAGE_INFO   = 0x0F,

# First protocol version with the firmware-update commands.
FW_UPDATE_MIN_PROTOCOL_VERSION = 2


class FwResult(enum.IntEnum):
    """Mirrors enum rec_fw_result (client/include/recom_fw_update.h)."""
    OK              = 0
    BUSY            = 1
    ERR_STATE       = 2
    ERR_PARAM       = 3
    ERR_SIZE        = 4
    ERR_BOUNDS      = 5
    ERR_ALIGN       = 6
    ERR_OVERLAP     = 7
    ERR_INCOMPLETE  = 8
    ERR_BAD_IMAGE   = 9
    ERR_UNCONFIRMED = 10
    ERR_FLASH       = 11
    ERR_UNSUPPORTED = 12


FW_RESULT_TEXT = {
    FwResult.OK: "ok",
    FwResult.BUSY: "device busy",
    FwResult.ERR_STATE: "not allowed in the device's current update state",
    FwResult.ERR_PARAM: "malformed request",
    FwResult.ERR_SIZE: "image size not accepted (too large or too small)",
    FwResult.ERR_BOUNDS: "write outside the image",
    FwResult.ERR_ALIGN: "misaligned write",
    FwResult.ERR_OVERLAP: "data already written",
    FwResult.ERR_INCOMPLETE: "image incomplete",
    FwResult.ERR_BAD_IMAGE: "image rejected by the device's checks",
    FwResult.ERR_UNCONFIRMED: "the running firmware is not yet confirmed "
                              "(a previous update is still on its test boot)",
    FwResult.ERR_FLASH: "device storage error",
    FwResult.ERR_UNSUPPORTED: "not supported by the device",
}


def fw_result_text(code) -> str:
    try:
        return FW_RESULT_TEXT[FwResult(code)]
    except ValueError:
        return f"unknown error {code}"


class FwState(enum.IntEnum):
    """Mirrors enum rec_fw_state."""
    IDLE        = 0
    PREPARING   = 1
    RECEIVING   = 2
    VERIFYING   = 3
    READY       = 4
    APPLIED     = 5
    ERROR       = 6


class FwApplyMode(enum.IntEnum):
    """Mirrors enum rec_fw_apply_mode."""
    TEST        = 0
    PERMANENT   = 1


@dataclass
class FwInfo:
    image_format: int
    max_chunk: int
    write_align: int
    max_image_size: int


@dataclass
class FwStatus:
    state: int
    busy: bool
    last_result: int
    op_error: int
    image_size: int
    bytes_received: int
    progress_done: int
    progress_total: int


@dataclass
class FwImageInfo:
    confirmed: bool
    version: Optional[ImageVersion]

# Chunk size for CMD_LOG_READ. Must not exceed the device's own
# control-transfer buffer (RECOM_INTERFACE_DATA_BUFFER_SIZE in
# client/include/recom_config.h, 64 bytes by default) -- a device may
# return less per chunk, never more.
LOG_READ_CHUNK_SIZE = 64

class RESET(enum.IntEnum):
    RCM_DEV_RST_REBOOT      = 0x00,     # Reset the device back to the application
    RCM_DEV_RST_BOOTLOADER  = 0x01,     # Reset to bootloader
    RCM_DEV_RST_ROM_BOOT    = 0x02,     # Reset to built-in ROM bootloader

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

    def close(self):
        """Releases the device (e.g. before it reboots)."""
        if self._comsBackend:
            self._comsBackend.close()

    @property
    def backend(self):
        return self._comsBackend

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

    def getLogBytes(self):
        """Reads and reassembles the device's currently available log as
        raw bytes.

        Reads CMD_LOG_READ in LOG_READ_CHUNK_SIZE chunks starting at
        offset 0 (the oldest byte available), advancing by the bytes
        actually returned each time, until a chunk comes back short --
        which also correctly ends a log whose length is an exact
        multiple of the chunk size, since the next read then returns 0.

        The device may keep logging while this runs, so the result is a
        best-effort snapshot, not an atomic one.
        """
        chunks = []
        offset = 0
        while True:
            data = self._comsBackend.read(BASE_DEV_CMDS.CMD_LOG_READ, index=offset,
                                          dataLen=LOG_READ_CHUNK_SIZE)
            if data:
                chunks.append(bytes(data))
            if len(data) < LOG_READ_CHUNK_SIZE:
                break
            offset += len(data)
        return b"".join(chunks)

    def getLog(self):
        """The device's log as whole, timestamp-ordered records, ready to
        print (one record per line, newline-terminated).

        The raw bytes from getLogBytes() are carved from a ring buffer and
        so usually start partway through a line, and can carry a torn last
        line or briefly out-of-order lines; recom.log.format_log() drops
        the partials and orders the rest. Use getLogBytes() for the
        unprocessed blob.
        """
        return format_log(self.getLogBytes())

    # ---------------------------------------------------------------- #
    # Firmware update (see client/include/recom_fw_update.h for the
    # device side and payload layouts). recom.fw_update drives these.
    # ---------------------------------------------------------------- #

    def _fw_write(self, cmd, data=b'', value=0, index=0):
        """Sends a firmware-update write request. A refused request comes
        back as a bare STALL; the reason is read from FW_STATUS."""
        try:
            self._comsBackend.write(cmd, data, value=value, index=index)
        except RecomDeviceException.RequestRejected:
            # Support itself was established by getFwInfo(); if the reason
            # can't be read now, the device went away mid-request (a
            # disconnect can surface as a STALL too).
            try:
                result = self.getFwStatus().last_result
            except RecomDeviceException.TransportException as e:
                raise RecomDeviceException.TransportException(
                    f"device stopped responding ({e})") from None
            raise RecomDeviceException.FwUpdateError(fw_result_text(result), result) from None

    def getFwInfo(self) -> FwInfo:
        try:
            data = bytes(self._comsBackend.read(BASE_DEV_CMDS.CMD_FW_INFO, dataLen=12))
        except RecomDeviceException.RequestRejected:
            raise RecomDeviceException.FwUpdateNotSupported(
                "device does not support firmware update") from None
        if len(data) < 12:
            raise RecomDeviceException.FwUpdateError("short FW_INFO response")
        _ver, fmt, max_chunk, write_align, _rsv, max_size = struct.unpack('<BBHHHI', data[:12])
        return FwInfo(fmt, max_chunk, write_align, max_size)

    def getFwStatus(self) -> FwStatus:
        data = bytes(self._comsBackend.read(BASE_DEV_CMDS.CMD_FW_STATUS, dataLen=16))
        if len(data) < 16:
            raise RecomDeviceException.FwUpdateError("short FW_STATUS response")
        (state, flags, last_result, op_error, image_size, received,
         done, total) = struct.unpack('<BBBBIIHH', data[:16])
        return FwStatus(state, bool(flags & 0x01), last_result, op_error, image_size,
                        received, done, total)

    def getFwImageInfo(self) -> FwImageInfo:
        try:
            data = bytes(self._comsBackend.read(BASE_DEV_CMDS.CMD_FW_IMAGE_INFO, dataLen=12))
        except RecomDeviceException.RequestRejected:
            raise RecomDeviceException.FwUpdateNotSupported(
                "device does not report its firmware image") from None
        if len(data) < 12:
            raise RecomDeviceException.FwUpdateError("short FW_IMAGE_INFO response")
        flags, major, minor, _rsv, revision, _rsv2, build = struct.unpack('<BBBBHHI', data[:12])
        version = ImageVersion(major, minor, revision, build) if flags & 0x02 else None
        return FwImageInfo(bool(flags & 0x01), version)

    def fwBegin(self, image_size: int):
        self._fw_write(BASE_DEV_CMDS.CMD_FW_BEGIN, struct.pack('<I', image_size))

    def fwWrite(self, offset: int, chunk: bytes):
        # The 32-bit offset travels in the request's value (high half) and
        # index (low half) fields.
        self._fw_write(BASE_DEV_CMDS.CMD_FW_DATA, chunk,
                       value=(offset >> 16) & 0xFFFF, index=offset & 0xFFFF)

    def fwFinish(self):
        self._fw_write(BASE_DEV_CMDS.CMD_FW_FINISH)

    def fwApply(self, mode: int = FwApplyMode.TEST):
        self._fw_write(BASE_DEV_CMDS.CMD_FW_APPLY, struct.pack('B', mode))

    def fwAbort(self):
        self._fw_write(BASE_DEV_CMDS.CMD_FW_ABORT)


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
            d = be.find(**kwargs)
            if d is not None:
                dev_list.extend(d)
        if dev_list == []:
            raise RecomDeviceException.NoDeviceFound
        if len(dev_list) > 1:
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
        return self._comsBackend.get_device_path()
