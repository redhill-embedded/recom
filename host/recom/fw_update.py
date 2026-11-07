"""Firmware update over RECom.

``update_firmware()`` runs the whole sequence against a RecomDevice:

  1. check the device supports it and the image fits (and, for MCUboot
     images, that the file is a well-formed image);
  2. begin -> wait while the device prepares (e.g. erases);
  3. send the image in chunks;
  4. finish -> wait while the device checks the image;
  5. apply (test or permanent) and reboot the device;
  6. wait for it to disconnect and come back (same port, or by serial
     number), reopen it and check the running image: the expected version,
     and -- for a test install -- that the device confirms it.

The device side is described in client/include/recom_fw_update.h. Nothing
here is specific to a particular MCU or bootloader.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from recom.device import (
    FW_UPDATE_MIN_PROTOCOL_VERSION,
    RESET,
    FwApplyMode,
    FwResult,
    FwState,
    RecomDevice,
    fw_result_text,
)
from recom.exceptions import RecomDeviceException
from recom.fw_image import FirmwareImage, ImageVersion, load_image

# Stage names passed to the progress callback.
STAGE_PREPARE = "prepare"
STAGE_SEND = "send"
STAGE_VERIFY = "verify"
STAGE_REBOOT = "reboot"
STAGE_RECONNECT = "reconnect"
STAGE_CONFIRM = "confirm"

ProgressCallback = Callable[[str, int, int], None]

STATUS_POLL_INTERVAL = 0.05
CONFIRM_POLL_INTERVAL = 0.5
CHUNK_RETRIES = 3


@dataclass
class UpdateResult:
    success: bool
    message: str
    previous_version: Optional[ImageVersion] = None
    expected_version: Optional[ImageVersion] = None
    running_version: Optional[ImageVersion] = None
    confirmed: Optional[bool] = None
    device: Optional[RecomDevice] = None    # the reopened device, if any


class FwUpdateFailed(Exception):
    """Update failed; the message says at which step and why."""


def _no_progress(stage, done, total):
    pass


def _wait_idle(dev, progress: ProgressCallback, stage: str, timeout: float,
               want_state: int):
    """Polls FW_STATUS until the device is no longer busy, then checks it
    reached ``want_state``."""
    deadline = time.monotonic() + timeout
    while True:
        st = dev.getFwStatus()
        progress(stage, st.progress_done, st.progress_total)
        if st.state == FwState.ERROR:
            raise FwUpdateFailed(f"{stage}: {fw_result_text(st.op_error)}")
        if not st.busy:
            if st.state != want_state:
                raise FwUpdateFailed(f"{stage}: device ended in state "
                                     f"{FwState(st.state).name}, expected "
                                     f"{FwState(want_state).name}")
            return st
        if time.monotonic() > deadline:
            raise FwUpdateFailed(f"{stage}: device still busy after {timeout:.0f} s")
        time.sleep(STATUS_POLL_INTERVAL)


def _send(dev, image: FirmwareImage, chunk: int, progress: ProgressCallback):
    total = image.size
    offset = 0
    while offset < total:
        data = image.data[offset:offset + chunk]
        for attempt in range(CHUNK_RETRIES):
            try:
                dev.fwWrite(offset, data)
                break
            except RecomDeviceException.FwUpdateError as e:
                # A retried chunk the device did receive the first time.
                if attempt > 0 and e.result == FwResult.ERR_OVERLAP:
                    break
                raise FwUpdateFailed(f"send (offset {offset}): {e}") from None
            except RecomDeviceException.TransportException:
                if attempt == CHUNK_RETRIES - 1:
                    raise
        offset += len(data)
        progress(STAGE_SEND, offset, total)


def _reopen(descriptor, timeout: float, open_device) -> RecomDevice:
    """Opens the re-attached device; its driver may take a moment."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return open_device(device=descriptor)
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


def update_firmware(dev: RecomDevice, image_path: str, *,
                    permanent: bool = False,
                    wait: bool = True,
                    reboot_timeout: float = 60.0,
                    confirm_timeout: float = 60.0,
                    progress: Optional[ProgressCallback] = None,
                    open_device=RecomDevice) -> UpdateResult:
    """Updates ``dev`` with the image at ``image_path``. See the module
    docstring. With ``wait=False`` it returns right after rebooting the
    device. Raises FwUpdateFailed (or RecomDeviceException.FwUpdateNotSupported)
    if the update could not be carried out; a device that comes back with
    the old image is reported through UpdateResult.success == False."""
    progress = progress or _no_progress

    if dev.protocol_version < FW_UPDATE_MIN_PROTOCOL_VERSION:
        raise RecomDeviceException.FwUpdateNotSupported(
            f"device speaks RECom protocol version {dev.protocol_version}; "
            f"firmware update needs version {FW_UPDATE_MIN_PROTOCOL_VERSION}")

    info = dev.getFwInfo()
    image = load_image(image_path, info.image_format)
    if image.size > info.max_image_size:
        raise FwUpdateFailed(f"image is {image.size} bytes; the device accepts at most "
                             f"{info.max_image_size}")

    try:
        previous = dev.getFwImageInfo().version
    except RecomDeviceException.FwUpdateNotSupported:
        previous = None

    identity = dev.backend.get_identity()
    backend_cls = type(dev.backend)

    # Clear whatever an interrupted earlier session may have left behind.
    if dev.getFwStatus().state != FwState.IDLE:
        dev.fwAbort()

    try:
        dev.fwBegin(image.size)
    except RecomDeviceException.FwUpdateError as e:
        raise FwUpdateFailed(f"begin: {e}") from None
    _wait_idle(dev, progress, STAGE_PREPARE, 60.0, FwState.RECEIVING)

    align = max(1, info.write_align)
    chunk = max(align, info.max_chunk - info.max_chunk % align)
    _send(dev, image, chunk, progress)

    try:
        dev.fwFinish()
    except RecomDeviceException.FwUpdateError as e:
        raise FwUpdateFailed(f"finish: {e}") from None
    _wait_idle(dev, progress, STAGE_VERIFY, 60.0, FwState.READY)

    try:
        dev.fwApply(FwApplyMode.PERMANENT if permanent else FwApplyMode.TEST)
    except RecomDeviceException.FwUpdateError as e:
        raise FwUpdateFailed(f"apply: {e}") from None

    progress(STAGE_REBOOT, 0, 1)
    try:
        dev.reset(RESET.RCM_DEV_RST_REBOOT)
    except Exception:
        # The device may reset before the host sees the request complete.
        pass
    dev.close()

    if not wait:
        return UpdateResult(True, "image sent; device rebooting to install it",
                            previous, image.version)

    if not backend_cls.wait_for_disconnect(identity, 10.0):
        raise FwUpdateFailed("reboot: device did not disconnect")
    progress(STAGE_RECONNECT, 0, 1)
    descriptor = backend_cls.wait_for_reconnect(identity, reboot_timeout)
    if descriptor is None:
        raise FwUpdateFailed(f"reconnect: device did not come back within {reboot_timeout:.0f} s")
    new_dev = _reopen(descriptor, 10.0, open_device)

    info_after = new_dev.getFwImageInfo()
    running = info_after.version
    result = UpdateResult(False, "", previous, image.version, running,
                          info_after.confirmed, new_dev)

    if image.version is not None and running != image.version:
        if running is not None and running == previous:
            result.message = ("device is still running the previous firmware "
                              f"({running}): the bootloader rejected the new image "
                              "or reverted it")
        else:
            result.message = (f"device is running {running}, "
                              f"expected {image.version}")
        return result

    # A test install must confirm itself; wait for it.
    deadline = time.monotonic() + confirm_timeout
    while not info_after.confirmed:
        progress(STAGE_CONFIRM, 0, 1)
        if time.monotonic() > deadline:
            result.message = (f"device runs {running} but did not confirm it within "
                              f"{confirm_timeout:.0f} s; it will revert on its next reset")
            return result
        time.sleep(CONFIRM_POLL_INTERVAL)
        info_after = new_dev.getFwImageInfo()
    progress(STAGE_CONFIRM, 1, 1)

    result.success = True
    result.confirmed = True
    result.message = f"updated to {running}" if running else "updated"
    return result
