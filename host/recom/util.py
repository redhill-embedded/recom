import pyudev
import psutil

from serial.tools import list_ports

from recom import RecomDevice


def get_drive_mount_point_from_usb_port_path(port_path: list, vid_pid=tuple)-> str:
    """Utility function to get the storage drive mount point of a USB device
    
    port_path is a list of port numbers indicating the USB device's path oon the bus
    vid_pid is a tuple containig the device's VID/PID.

    If the device described by the provided parameters has a mass-storage partition
    mounted on the system, then its mount point will be returned.
    Otherwise, returns None.
    """
    ctx = pyudev.Context()
    # Loop through all disk/block devices in the system
    for dev in ctx.list_devices(subsystem='block'):
        try:
            path = dev.get('ID_PATH').split(':')
            match_found = False
            # Look for a device on the specified USB port path
            for i in range(len(path)):
                if 'usb' in path[i]:
                    usb_path = path[i+1].split('.')
                    usb_path = [int(x) for x in usb_path]
                    if usb_path == port_path:
                        match_found = True
                        break
            if not match_found:
                continue
            # Now check that the VID/PID match
            if dev.get('ID_VENDOR_ID') == format(vid_pid[0], 'x') and \
               dev.get('ID_MODEL_ID') == format(vid_pid[1], '04x'):
                pass
            else:
                continue
            # If we get here then we have found a device matching our criteria.
            # Now find it's mountpoint
            for partition in dev.children:
                if 'ID_FS_TYPE' in partition:
                    dev_name = partition.get('DEVNAME')
                    context = psutil.disk_partitions(all=True)
                    for partition in context:
                        if partition.device == dev_name:
                            return partition.mountpoint
        except Exception:
            continue
        return None

def get_serial_port_list(device: RecomDevice):
    """Returns a list of all serial ports (if any) that are part of this device

    The returned values are strings describing the port's device name (i.e. ttyUSB0 or COM7)
    """
    port_match_gen = list_ports.grep(device.device_path)
    return [port.device for port in port_match_gen]
