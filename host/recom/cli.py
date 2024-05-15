import argparse
import os
import platform
import sys
import sysconfig
import subprocess
from datetime import datetime

import recom
from recom.device import RecomDevice, RecomDeviceException
from recom.device import RESET
from recom.backend import backends

def print_recom_dev_info(dev, verbose):
    print("%s - HW ID/Rev: 0x%04X / 0x%04X" % (dev, dev.hw_id, dev.hw_revision))
    if verbose:
        # Recom information
        print("  Recom protocol version = %d" % dev.protocol_version)
        print("  Recom FW version: %s" % dev.recom_fw_version)
        # Device information
        print("  HW ID/Rev: 0x%04X / 0x%04X" % (dev.hw_id, dev.hw_revision))
        print("  FW Rev: %s" % dev.fw_revision)
        print("  Serial: %s" % dev.get_serial())
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
        except RecomDeviceException as dev_exp:
            print(dev_exp)
            return
    else:
        print(f'Find by DeviceID - {device_id}')
        try:
            dev = RecomDevice(id=device_id)
        except RecomDeviceException:
            return

    print_recom_dev_info(dev, verbose)

def run_scan(verbose):
    print("Scanning for Recom devices...")
    dev_list = []
    for be in backends:
        be_devices = be.find()
        if be_devices is not None:
            dev_list.extend(be_devices)
    for s_dev in dev_list:
        try:
            dev = RecomDevice(device=s_dev)
        except Exception:
            pass
        else:
            print_recom_dev_info(dev, verbose)

def reset_device(reset_option, device_id, serial):
    try:
        dev = RecomDevice(id=device_id, serial=serial)
    except RecomDeviceException as dev_exp:
        print(dev_exp)
        return
    dev.reset(reset_option)

def diag_env(save_report=False):
    # System Information
    print(f"\nSystem Information:")
    print(f"\tMachine: {platform.machine()}")
    print(f"\tSystem: {platform.system()}")
    print(f"\tRelease: {platform.release()}")
    print(f"\tVersion: {platform.version()}")
    print(f"\tArchitecture: {platform.architecture()}")

    # Python Configuration
    print(f"\nPython Configuration:")
    print(f"\tPython Version: {platform.python_version()}")

    # Python Virtual Environment
    print(f"\nPython Virtual Environment:")
    print("\tVirtual Environment: {}".format(os.environ.get('VIRTUAL_ENV', "Not in a virtual environment")))
    if 'VIRTUAL_ENV' in os.environ:
        print(f"\tPython Version in Virtual Environment:")
        for item in sys.version.split("\n"):
            print("\t\t{}".format(item))
    
    if save_report:
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        file_name = "environment_info_{}.txt".format(timestamp)
        
        with open(file_name, 'w') as f:
            # System Information
            f.write("System Information:\n")
            f.write("\tMachine: {}\n".format(platform.machine()))
            f.write("\tSystem: {}\n".format(platform.system()))
            f.write("\tRelease: {}\n".format(platform.release()))
            f.write("\tVersion: {}\n".format(platform.version()))
            f.write("\tArchitecture: {}\n".format(platform.architecture()))

            # Python Configuration
            f.write("\nPython Configuration:\n")
            f.write("\tPython Version: {}\n".format(platform.python_version()))

            # Python Virtual Environment
            f.write("\nPython Virtual Environment:\n")
            f.write("\tVirtual Environment: {}".format(os.environ.get('VIRTUAL_ENV', "Not in a virtual environment")))
            if 'VIRTUAL_ENV' in os.environ:
                f.write("\tPython Version in Virtual Environment:\n")
                for item in sys.version.split("\n"):
                    f.write("\t\t{}\n".format(item))

            # Installed Libraries and Versions
            f.write("\nInstalled Packages:\n")
            installed_packages = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze']).decode().split('\n')
            for package in installed_packages:
                f.write("\t{}\n".format(package))

            # Environment Variables
            f.write("Environment Variables:\n")
            for key, value in os.environ.items():
                f.write("\t{}: {}".format(key, value))

            f.write("\tCompiler: {}\n".format(sys.version.split()[0]))
            f.write("\tCompiler Flags: {}\n".format(sys.flags))
            f.write("\tPy_ENABLE_SHARED: {}\n".format(sysconfig.get_config_var('Py_ENABLE_SHARED')))

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
    parser.add_argument("cmd", type=str, help="Command/Action")
    parser.add_argument('--version', action='version', version=recom.__version__,
                                                help="Print package version")
    parser.add_argument('-d', '--device', default=None, help='Device ID to search for ([VID:PID] for USB, port for serial)')
    parser.add_argument('-S', '--serial', default=None, help='Serial number to search for')
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase verbosity")
    parser.add_argument("--report", action="store_true", help="Write env report to file")

    args, remaining_args = parser.parse_known_args(argv)

    if args.cmd == "scan":
        run_scan(args.verbose)
    elif args.cmd == "find":
        if args.device is not None or args.serial is not None:
            list_devices(args.device, args.serial, args.verbose)
        else:
            print("Please provide either a device ID or a device serial number")
    elif args.cmd == "reset":
        if remaining_args:
            # Unknown arguments are present. Assume the first one is the reset option
            rst_opt = int(remaining_args[0])
        else:
            print("No reset option provided. Defaulting to rebooting device to application.")
            rst_opt = RESET.RCM_DEV_RST_REBOOT
        if args.device is not None or args.serial is not None:
            reset_device(rst_opt, args.device, args.serial)
        else:
            print("Please provide either a device ID or a device serial number")
    elif args.cmd == "env":
        diag_env(args.report)
    else:
        print_info()
