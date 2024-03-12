import argparse

import recom
from recom.device import RecomDevice, DeviceException

def list_devices(device_id, serial):
    dev = None
    print("Finding device")
    if serial is not None:
        print(f'Find by serial - {serial}')
        try:
            dev = RecomDevice(serial=serial)
        except DeviceException as dev_exp:
            print(dev_exp)
            return

    else:
        print(f'Find by DeviceID - {device_id}')
        try:
            dev = RecomDevice(device_id=device_id)
        except DeviceException as dev_exp:
            print(dev_exp)
            return

    print("Found device: %s" % dev)

    print("\tHW ID/Rev: 0x%04X / 0x%04X" % (dev.hw_id, dev.hw_revision))
    print("\tFW Rev: %s" % dev.fw_revision)
    print("\tSerial: %s" % dev.serial)
    print("\n\tInterfaces:")
    interfaces = dev.getAllInterfaces()
    for itf in interfaces:
        itf_tuple = (itf[1], itf[2])
        itf_handle = dev.getInterfaceHandleFromID(itf_tuple)
        print("\t\t%s" % itf_handle)


def cli(argv):
    parser = argparse.ArgumentParser(description="Open a serial port and read/write data.")
    parser.add_argument('--version', action='version', version=recom.__version__,
                                                help="Print package version")
    parser.add_argument('-d', '--device', help='Device ID to search for ([VID:PID] for USB, port for serial)')
    parser.add_argument('-S', '--serial', help='Serial number to search for')

    args = parser.parse_args(argv)

    list_devices(args.device, args.serial)