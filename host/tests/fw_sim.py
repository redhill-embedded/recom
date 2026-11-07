"""A simulated RECom device implementing the firmware-update protocol, for
testing recom.fw_update without hardware.

It behaves like a device with an A/B bootloader: the image is stored,
checked, applied, and installed on reboot; a test install then confirms
itself after a few FW_IMAGE_INFO polls. Knobs select failure scenarios.
"""

import struct

from recom.backend.backend import DeviceIdentity, RecomBackend, RecomDeviceDescriptor
from recom.device import BASE_DEV_CMDS, RESET, FwResult, FwState, RecomDevice
from recom.exceptions import RecomDeviceException
from recom.fw_image import MCUBOOT_IMAGE_MAGIC, ImageVersion


def mcuboot_image(body_len=1000, version=(1, 2, 3, 4), prot_tlvs=False, hdr_size=0x40):
    """Builds a structurally valid MCUboot image (signature bytes are
    dummies -- the host doesn't verify them)."""
    major, minor, rev, build = version
    body = bytes((i * 7 + 3) & 0xFF for i in range(body_len))
    prot = b""
    if prot_tlvs:
        tlv = struct.pack("<HH", 0x50, 4) + b"\x07\x00\x00\x00"
        prot = struct.pack("<HH", 0x6908, 4 + len(tlv)) + tlv
    hdr = struct.pack("<IIHHII BBHI I", MCUBOOT_IMAGE_MAGIC, 0, hdr_size, len(prot),
                      body_len, 0, major, minor, rev, build, 0)
    hdr += b"\x00" * (hdr_size - len(hdr))
    tlvs = struct.pack("<HH", 0x10, 32) + b"\xAA" * 32 + struct.pack("<HH", 0x22, 70) + b"\x55" * 70
    unprot = struct.pack("<HH", 0x6907, 4 + len(tlvs)) + tlvs
    return hdr + body + prot + unprot


class SimDevice:
    """Device-side state shared across (simulated) reboots."""

    def __init__(self, running=(1, 0, 0, 0), confirmed=True, max_image=64 * 1024,
                 max_chunk=512, write_align=16, image_format=1, protocol_version=2):
        self.running = ImageVersion(*running)
        self.confirmed = confirmed
        self.max_image = max_image
        self.max_chunk = max_chunk
        self.write_align = write_align
        self.image_format = image_format
        self.protocol_version = protocol_version
        # Failure knobs
        self.supports_fw = True
        self.bootloader_rejects = False     # new image never boots
        self.never_confirms = False
        self.comes_back = True
        self.verify_error = None            # FwResult raised during verify
        self.transient_failures = {}        # offset -> times to fail with a transport error
        self.drop_after_write = set()       # offsets: write lands, but the host sees an error
        self.vanish_at = None               # offset: device disappears; every request
                                            # after that stalls (as a disconnect can)
        self.erase_steps = 3
        self.confirm_after_polls = 2
        # Update session
        self.state = FwState.IDLE
        self.busy_polls = 0
        self.op_error = 0
        self.last_result = 0
        self.size = 0
        self.buf = None
        self.written = set()
        self.apply_mode = None
        self.boot_count = 0
        self.info_polls = 0
        self.aborts = 0
        self.writes = 0
        self.connected = True
        self.address = 5

    # ---------------------------------------------------------------- #

    def reboot(self):
        self.boot_count += 1
        self.address += 1
        if self.state == FwState.APPLIED and not self.bootloader_rejects:
            hdr = bytes(self.buf[:32])
            _m, _l, _h, _p, _i, _f, major, minor, rev, build, _pad = struct.unpack(
                "<IIHHII BBHI I", hdr)
            self.running = ImageVersion(major, minor, rev, build)
            self.confirmed = self.apply_mode == 1
            self.info_polls = 0
        self.state = FwState.IDLE
        self.connected = self.comes_back

    def request_write(self, cmd, data, value, index):
        if not self.supports_fw and cmd >= BASE_DEV_CMDS.CMD_FW_INFO:
            raise RecomDeviceException.RequestRejected("stall")
        if cmd == BASE_DEV_CMDS.CMD_RESET:
            if data[0] == RESET.RCM_DEV_RST_REBOOT:
                self.reboot()
            return
        result = self._fw_write(cmd, bytes(data), (value << 16) | index)
        self.last_result = result
        if result != FwResult.OK:
            raise RecomDeviceException.RequestRejected("stall")

    def _fw_write(self, cmd, data, offset):
        if cmd == BASE_DEV_CMDS.CMD_FW_BEGIN:
            if self.state != FwState.IDLE:
                return FwResult.ERR_STATE
            if not self.confirmed:
                return FwResult.ERR_UNCONFIRMED
            (size,) = struct.unpack("<I", data)
            if size == 0 or size > self.max_image:
                return FwResult.ERR_SIZE
            self.size, self.buf, self.written = size, bytearray(b"\xff" * size), set()
            self.state, self.busy_polls = FwState.PREPARING, self.erase_steps
            return FwResult.OK
        if cmd == BASE_DEV_CMDS.CMD_FW_DATA:
            if self.state != FwState.RECEIVING:
                return FwResult.ERR_STATE
            if offset % self.write_align:
                return FwResult.ERR_ALIGN
            if offset + len(data) > self.size:
                return FwResult.ERR_BOUNDS
            if len(data) % self.write_align and offset + len(data) != self.size:
                return FwResult.ERR_ALIGN
            units = set(range(offset // self.write_align,
                              (offset + len(data) + self.write_align - 1) // self.write_align))
            if units & self.written:
                return FwResult.ERR_OVERLAP
            self.buf[offset:offset + len(data)] = data
            self.written |= units
            self.writes += 1
            if offset in self.drop_after_write:
                self.drop_after_write.discard(offset)
                raise RecomDeviceException.TransportException("timeout after write")
            return FwResult.OK
        if cmd == BASE_DEV_CMDS.CMD_FW_FINISH:
            if self.state != FwState.RECEIVING:
                return FwResult.ERR_STATE
            needed = (self.size + self.write_align - 1) // self.write_align
            if len(self.written) != needed:
                return FwResult.ERR_INCOMPLETE
            self.state, self.busy_polls = FwState.VERIFYING, 2
            return FwResult.OK
        if cmd == BASE_DEV_CMDS.CMD_FW_APPLY:
            if self.state != FwState.READY:
                return FwResult.ERR_STATE
            self.apply_mode = data[0]
            self.state = FwState.APPLIED
            return FwResult.OK
        if cmd == BASE_DEV_CMDS.CMD_FW_ABORT:
            self.aborts += 1
            self.state = FwState.IDLE
            return FwResult.OK
        return FwResult.ERR_PARAM

    def status(self):
        if self.busy_polls:
            self.busy_polls -= 1
            if self.busy_polls == 0:
                if self.state == FwState.PREPARING:
                    self.state = FwState.RECEIVING
                elif self.state == FwState.VERIFYING:
                    if self.verify_error is not None:
                        self.state, self.op_error = FwState.ERROR, self.verify_error
                    else:
                        self.state = FwState.READY
        busy = self.busy_polls > 0
        return struct.pack("<BBBBIIHH", self.state, 1 if busy else 0, self.last_result,
                           self.op_error, self.size, len(self.written) * self.write_align,
                           self.erase_steps - self.busy_polls, self.erase_steps)

    def image_info(self):
        self.info_polls += 1
        if (not self.confirmed and not self.never_confirms
                and self.info_polls > self.confirm_after_polls):
            self.confirmed = True
        v = self.running
        flags = (1 if self.confirmed else 0) | 2
        return struct.pack("<BBBBHHI", flags, v.major, v.minor, 0, v.revision, 0, v.build)

    def request_read(self, cmd, value, index, length):
        if cmd == BASE_DEV_CMDS.CMD_RECOM_DEV_ID:
            return struct.pack("<IH", 0x53C08A30, self.protocol_version) + b"sim"
        if not self.supports_fw and cmd >= BASE_DEV_CMDS.CMD_FW_INFO:
            raise RecomDeviceException.RequestRejected("stall")
        if cmd == BASE_DEV_CMDS.CMD_FW_INFO:
            return struct.pack("<BBHHHI", 1, self.image_format, self.max_chunk,
                               self.write_align, 0, self.max_image)
        if cmd == BASE_DEV_CMDS.CMD_FW_STATUS:
            return self.status()
        if cmd == BASE_DEV_CMDS.CMD_FW_IMAGE_INFO:
            return self.image_info()
        if cmd == BASE_DEV_CMDS.CMD_SERIAL:
            return b"SIM0001"
        raise RecomDeviceException.RequestRejected("stall")


class SimBackend(RecomBackend):
    """RecomBackend over a SimDevice."""

    def __init__(self, sim: SimDevice):
        self.sim = sim
        self.closed = False

    @classmethod
    def type(cls):
        return "sim"

    def open(self):
        pass

    def close(self):
        self.closed = True

    def read(self, request, value=0, index=0, dataLen=512, timeout=1000):
        if self.sim.vanish_at == -1:
            raise RecomDeviceException.RequestRejected("stall")
        return self.sim.request_read(request, value, index, dataLen)

    def write(self, request, data=b'', value=0, index=0, timeout=1000):
        failures = self.sim.transient_failures
        if self.sim.vanish_at == -1:
            raise RecomDeviceException.RequestRejected("stall")
        if request == BASE_DEV_CMDS.CMD_FW_DATA:
            offset = (value << 16) | index
            if offset == self.sim.vanish_at:
                self.sim.vanish_at = -1
                raise RecomDeviceException.RequestRejected("stall")
            if failures.get(offset):
                failures[offset] -= 1
                raise RecomDeviceException.TransportException("timeout")
        return self.sim.request_write(request, data, value, index)

    def get_identity(self):
        return DeviceIdentity("sim", (0x1234, 0x5678), ("sim",), "SIM0001",
                              self.sim.address)

    def get_interface_list(self):
        return []

    # The simulator reboots synchronously inside the reset request.
    current_sim = None

    @classmethod
    def wait_for_disconnect(cls, identity, timeout):
        return True

    @classmethod
    def wait_for_reconnect(cls, identity, timeout):
        sim = cls.current_sim
        if sim is None or not sim.connected:
            return None
        return RecomDeviceDescriptor("sim", identity.dev_id, identity.location)


def sim_device(sim: SimDevice) -> RecomDevice:
    """A RecomDevice talking to ``sim`` (skipping backend discovery)."""
    dev = RecomDevice.__new__(RecomDevice)
    dev._interfaces = []
    dev._comsBackend = SimBackend(sim)
    info = dev.getRecomDevID()
    dev.protocol_version = info["protocol_version"]
    dev.recom_fw_version = info["version_string"]
    SimBackend.current_sim = sim
    return dev


def sim_opener(sim: SimDevice):
    """``open_device`` replacement for update_firmware(): reopens ``sim``."""
    def open_device(device=None):
        return sim_device(sim)
    return open_device
