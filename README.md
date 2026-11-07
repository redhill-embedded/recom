# recom

## Firmware update

RECom can update a device's firmware over its RECom connection:

    pip install recom
    recom update -d VID:PID firmware.bin        # or -S SERIAL to pick one device

The host tool checks the image against what the device reports it accepts,
sends it, has the device verify it, tells the device to install it, and
reboots the device. It then waits for the device to disconnect and come
back, on the same USB port or, by serial number, on another one. It reads the
running firmware version and waits until the device confirms the new image.
It exits non-zero if any step fails, including when the device comes back
still running the old firmware.

Options: `--permanent` installs without a test boot. `--no-wait` returns
once the device reboots. `--timeout S` bounds the reconnect and
confirmation waits (default 60 s).

The same sequence is available as a library call:
`recom.fw_update.update_firmware(RecomDevice(id="VID:PID"), "firmware.bin")`.

### Device side

RECom only transports the image and runs the workflow. The application
stores, checks and installs it by implementing the weak callbacks in
[`client/include/recom_fw_update.h`](client/include/recom_fw_update.h)
(`rec_device_fw_info_cb()`, `..._begin_cb()`, `..._write_cb()`,
`..._finish_cb()`, `..._apply_cb()`, `..._abort_cb()`, `..._status_cb()`,
`..._image_info_cb()`). RECom makes no assumption about the MCU, flash or
bootloader. The header documents the requests and payloads.

- Callbacks must return quickly. Slow work such as erasing or hashing is
  reported as `busy` in the status and advanced from
  `rec_device_poll_cb()`, which `recom_task()` calls on every pass.
- `RECOM_CTRL_BUFFER_SIZE` (in `recom_config.h`, default 64) bounds the
  chunk size. Larger chunks transfer faster: 512 bytes gives about 40 KB/s
  over full-speed USB.
- The device reports the image format. For `MCUBOOT` images the host
  checks the file's MCUboot header and TLVs before sending and compares
  the version after reboot. `OPAQUE` images are sent as-is.
- Downgrades are allowed; the host doesn't compare versions for ordering.
- Firmware update needs RECom protocol version 2 on the device.

## Windows

RECom devices work on Windows 8.1 and later without installing a driver:

- The device's USB descriptors include Microsoft OS 2.0 descriptors that
  make Windows bind its built-in WinUSB driver automatically.
- The `libusb1` package that `pip install recom` pulls in bundles
  `libusb-1.0.dll`, so nothing else needs installing on the host.

To make this work, every RECom USB device has a built-in, endpoint-less
vendor interface as interface 0, named "RECom", which WinUSB binds to. It
carries no data; RECom's requests still go to the device.

Windows caches, per VID/PID/`bcdDevice`, whether a device has these
descriptors. A device that was plugged into a Windows machine before it
had them is not re-examined. In that case change `bcdDevice`, or delete
`HKLM\SYSTEM\CurrentControlSet\Control\usbflags\VVVVPPPPRRRR` (as
administrator) and re-plug the device.
