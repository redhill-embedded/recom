class RecomDeviceException(Exception):
    class NoDeviceFound(Exception):
        pass

    class MultipleDevicesFound(Exception):
        pass

    class InterfaceNotFound(Exception):
        pass

    class InterfaceNumOutOfRange(Exception):
        pass

    class AccessDenied(Exception):
        pass

    class NotARecomDevice(Exception):
        pass

    class TransportException(Exception):
        pass

    class RequestRejected(TransportException):
        """The device refused a request (a USB control request STALL)."""
        pass

    class FwUpdateNotSupported(Exception):
        """The device does not implement RECom firmware update."""
        pass

    class FwUpdateError(Exception):
        """A firmware-update step failed. ``result`` is the device's
        FwResult code, if it reported one."""
        def __init__(self, message, result=None):
            super().__init__(message)
            self.result = result

    class Generic(Exception):
        pass