# recom

Host-side Python package for RECom, a communication layer between a host
and embedded devices over USB or a serial port. It gives you an API for
talking to RECom-enabled boards and a `recom` command-line tool for
common tasks. The device-side C library lives in the same repository:
<https://github.com/redhill-embedded/recom>.

## Install

    pip install recom

Python 3.8 or later. On Windows no driver install is needed; see
[Windows](https://github.com/redhill-embedded/recom#windows) in the project
README.

## Command line

    recom scan                              # list RECom-enabled devices
    recom find -d VID:PID                   # or -S SERIAL
    recom log [-d VID:PID | -S SERIAL] [-f] # print (or follow) a device's log
    recom reset -d VID:PID [OPTION]         # reset/reboot a device
    recom update -d VID:PID firmware.bin    # update a device's firmware
    recom env [--report]                    # check the host environment

`recom --help` lists all options.

## Firmware update

    recom update -d VID:PID firmware.bin

The tool checks the image against what the device accepts, sends it, has
the device verify and install it, and reboots the device. It then waits for
the device to come back (on the same USB port or, by serial number, on
another one) and confirm the new image. It exits non-zero if any step
fails, including when the device comes back still running the old
firmware. `--permanent` installs without a test boot, `--no-wait`
returns once the device reboots, and `--timeout S` bounds the waits
(default 60 s).

The same sequence is available as a library call:

```python
from recom import RecomDevice
from recom.fw_update import update_firmware

update_firmware(RecomDevice(id="VID:PID"), "firmware.bin")
```

The device side of firmware update is described in the
[project README](https://github.com/redhill-embedded/recom#firmware-update).
