"""Firmware image inspection for ``recom update``.

The device says which image format it expects (``FwInfo.image_format``).
For MCUboot images the host checks the file before sending anything -- the
header and TLV layout must describe exactly this file -- and reads the
image version, which is later compared with what the device reports after
rebooting. Opaque images are sent as-is.

Only the parts of the MCUboot format needed for that are parsed here (no
imgtool dependency); signature verification is the device's job.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import ClassVar, Optional

# MCUboot image format constants (boot/bootutil/include/bootutil/image.h).
MCUBOOT_IMAGE_MAGIC = 0x96F3B83D
MCUBOOT_HEADER_FMT = "<IIHHII BBHI I"   # 32 bytes
MCUBOOT_HEADER_SIZE = struct.calcsize(MCUBOOT_HEADER_FMT)
MCUBOOT_TLV_INFO_MAGIC = 0x6907
MCUBOOT_TLV_PROT_INFO_MAGIC = 0x6908


class ImageFormat:
    """Mirrors enum rec_fw_image_format (client/include/recom_fw_update.h)."""
    OPAQUE = 0
    MCUBOOT = 1

    NAMES: ClassVar[dict] = {OPAQUE: "opaque", MCUBOOT: "MCUboot"}


@dataclass(frozen=True, order=True)
class ImageVersion:
    major: int
    minor: int
    revision: int
    build: int

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.revision}+{self.build}"


class ImageError(ValueError):
    """The file is not a valid image of the expected format."""


@dataclass
class FirmwareImage:
    data: bytes
    format: int
    version: Optional[ImageVersion] = None

    @property
    def size(self) -> int:
        return len(self.data)


def parse_mcuboot(data: bytes) -> ImageVersion:
    """Checks that ``data`` is exactly one MCUboot image and returns its
    version. Raises ImageError otherwise."""
    if len(data) < MCUBOOT_HEADER_SIZE:
        raise ImageError("file is too small for an MCUboot image header")
    (magic, _load_addr, hdr_size, prot_tlv_size, img_size, _flags,
     major, minor, revision, build, _pad) = struct.unpack_from(MCUBOOT_HEADER_FMT, data)
    if magic != MCUBOOT_IMAGE_MAGIC:
        raise ImageError("not an MCUboot image (bad header magic) -- was it signed?")
    if hdr_size < MCUBOOT_HEADER_SIZE:
        raise ImageError("MCUboot header size field is invalid")

    tlv_off = hdr_size + img_size
    if prot_tlv_size:
        if tlv_off + 4 > len(data):
            raise ImageError("MCUboot protected TLV area lies outside the file")
        magic, tot = struct.unpack_from("<HH", data, tlv_off)
        if magic != MCUBOOT_TLV_PROT_INFO_MAGIC or tot != prot_tlv_size:
            raise ImageError("MCUboot protected TLV area is malformed")
    unprot_off = tlv_off + prot_tlv_size
    if unprot_off + 4 > len(data):
        raise ImageError("MCUboot TLV area lies outside the file (truncated image?)")
    magic, tot = struct.unpack_from("<HH", data, unprot_off)
    if magic != MCUBOOT_TLV_INFO_MAGIC:
        raise ImageError("MCUboot TLV area is missing -- was the image signed?")
    if unprot_off + tot != len(data):
        raise ImageError("file size does not match the MCUboot image "
                         f"({unprot_off + tot} bytes described, {len(data)} in file)")
    return ImageVersion(major, minor, revision, build)


def load_image(path: str, image_format: int) -> FirmwareImage:
    """Reads a firmware file and checks it against the device's format."""
    with open(path, "rb") as f:
        data = f.read()
    if not data:
        raise ImageError("file is empty")
    if image_format == ImageFormat.MCUBOOT:
        return FirmwareImage(data, image_format, parse_mcuboot(data))
    return FirmwareImage(data, image_format)
