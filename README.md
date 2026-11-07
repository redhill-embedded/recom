# recom

RECom is a communication layer between a host and embedded devices over USB
or a serial port. The repository has two parts:

- [`client/`](client/): the device-side C library, linked into the firmware.
- [`host/`](host/): the `recom` Python package, an API for talking to
  RECom-enabled boards plus the `recom` command-line tool. Its
  [README](host/README.md) is the package description on PyPI.

## Install

    pip install recom

## Development

Work on the host package from `host/`:

    pip install -e .
    pip install -r requirements-dev.txt
    make test        # run the test suite
    make package     # build the sdist and wheel into dist/
    make publish     # build, then upload to PyPI with twine

The package is built with Hatchling, and its version comes from the git tags
via `hatch-vcs`. To release, tag the commit (e.g. `0.1.2`) and build from it.
Between tags the version says how far past the last tag the build is:

| State                     | Version                       |
|---------------------------|-------------------------------|
| On tag `0.1.1`            | `0.1.1`                       |
| 3 commits after `0.1.1`   | `0.1.1.post1.dev3+g<hash>`    |
| Uncommitted changes       | `.d<date>` appended           |

## Firmware update

RECom can update a device's firmware over its RECom connection, using the
`recom` host tool (see [Install](#install)):

    recom update -d VID:PID firmware.bin        # or -S SERIAL to pick one device

The host side (what the tool checks, its options, and the equivalent library
call) is described in [host/README.md](host/README.md#firmware-update).

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
- `RECOM_CTRL_BUFFER_SIZE` (default 64, set in `recom_defs.h`; override it
  in `recom_config.h`) bounds the chunk size. Larger chunks transfer faster: 512 bytes gives about 40 KB/s
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
