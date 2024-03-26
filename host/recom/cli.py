import argparse

import recom
from recom.device import RecomDevice, DeviceException
from recom.backend.usb import get_all_devices

def print_recom_dev_info(dev, verbose):
    print("%s - HW ID/Rev: 0x%04X / 0x%04X" % (dev, dev.hw_id, dev.hw_revision))
    if verbose:
        # Recom information
        print("  Recom protocol version = %d" % dev.protocol_version)
        print("  Recom FW version: %s" % dev.recom_fw_version)
        # Device information
        print("  HW ID/Rev: 0x%04X / 0x%04X" % (dev.hw_id, dev.hw_revision))
        print("  FW Rev: %s" % dev.fw_revision)
        print("  Serial: %s" % dev.serial)
        print("\n  Interfaces:")
        interfaces = dev.getAllInterfaces()
        for itf in interfaces:
            itf_tuple = (itf[1], itf[2])
            itf_handle = dev.getInterfaceHandleFromID(itf_tuple)
            print("    %s" % itf_handle)

def list_devices(device_id, serial, verbose):
    dev = None
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

    print_recom_dev_info(dev, verbose)

def run_scan(verbose):
    print("Scanning for Recom devices...")
    dev_list = get_all_devices()
    for s_dev in dev_list:
        try:
            dev = RecomDevice(dev_handle=s_dev)
        except Exception:
            pass
        else:
            print_recom_dev_info(dev, verbose)

def print_info():
    print(f"\n*****\nWelcome to Recom {recom.__version__}")
    print("\nRecom is most useful as an API to interract with Recom-enabled boards, but there are")
    print("a few useful things you can do with this command-line interface:")
    print("    - Scan for Recom-enabled boards ('--scan' option)")
    print("    - Look for a particular board based on its device ID (i.e. VID/PID) or serial number.")
    print("      Use the '-d' parameter to sepcify the device ID and '-S' for the serial number.")
    print("*****\n")

def cli(argv):
    parser = argparse.ArgumentParser(description="Open a serial port and read/write data.")
    parser.add_argument('--version', action='version', version=recom.__version__,
                                                help="Print package version")
    parser.add_argument('-d', '--device', default=None, help='Device ID to search for ([VID:PID] for USB, port for serial)')
    parser.add_argument('-S', '--serial', default=None, help='Serial number to search for')
    parser.add_argument("--scan", action="store_true", help="Scan for Recom-enabled boards")
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase verbosity")

    args = parser.parse_args(argv)

    if args.scan:
        run_scan(args.verbose)
    elif args.device is not None or args.serial is not None:
        list_devices(args.device, args.serial, args.verbose)
    else:
        print_info()
