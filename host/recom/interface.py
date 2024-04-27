import enum

class RecomInterface:

    def __init__(self, deviceHandle, interfaceHandle):
        self._parentDevice = deviceHandle
        self._handle = interfaceHandle

    def __repr__(self):
        return f"Interface: {self.name} (Sub={self._handle.itf_subclass}/Prot={self._handle.itf_protocol})"

    def read(self, dataLen=-1):
        """
        Reads data from the interface's data endpoint
        
        dataLen specifies how many bytes should be read. If not speciied, any
        available bytes will be returned
        """
        if dataLen == -1:
            return self._handle.read()
        else:
            return self._handle.read(dataLen)
    
    def write(self, data):
        """
        Writes data to the interface's data endpoint

        Returns the number of bytes written to the interface
        """
        return self._handle.write(data)

    def controlRead(self, request, value=0, index=0, dataLen=64, timeout=1000):
        """Reads data from the interface's control endpoint"""
        return self._handle.controlRead(request=request,
                                        value=value,
                                        index=index,
                                        dataLen=dataLen,
                                        timeout=timeout)

    def controlWrite(self, request, data=b'', value=0, index=0, timeout=1000):
        """Writes data to the interface's control endpoint"""
        return self._handle.controlWrite(request=request,
                                         data=data,
                                         value=value,
                                         index=index,
                                         timeout=timeout)

    @property
    def name(self):
        return self._handle.itf_string
