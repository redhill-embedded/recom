import enum

class DeviceInterface:

    def __init__(self, deviceHandle, interfaceDescriptor):
        self._handle = deviceHandle
        self._descriptor = interfaceDescriptor

    def read(self, dataLen=-1, data=None):
        """
        Reads data from the interface
        
        dataLen specifies how many bytes should be read. If not speciied, any
        available bytes will be returned
        data is optional data that is sent before reading
        """
        return self._handle.read(dataLen, data)
    
    def write(self, data):
        """
        Writes data to the interface

        Returns the number of bytes written to the interface
        """
        return self._handle.write(data)

    @property
    def name(self):
        return self._descriptor('name')

    @property
    def id(self):
        return self._descriptor('id')