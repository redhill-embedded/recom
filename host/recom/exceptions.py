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

    class Generic(Exception):
        pass