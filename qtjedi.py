# Module implementing the JEDI serial communication protocol that work with 
# the QT framework for emitting a signal when new data packets are available.
#
# Author: Sivakumar Balasubramanian
# Date: 24 July 2024
# Email: siva82kb@gmail.com


import serial
import enum
import sys
import time
from serial.tools.list_ports import comports
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QThread)

_INDEBUG = False
_OUTDEBUG = False

class JediParsingStates(enum.Enum):
    LookingForHeader = 0
    FoundHeader1 = 1
    FoundHeader2 = 2
    ReadingPayload = 3
    CheckCheckSum = 4
    FoundFullPacket = 5


class JediComm(QThread):

    newdata_signal = pyqtSignal(list)

    def __init__(self, port=None, baudrate=115200) -> None:
        super().__init__()
        self._port = port
        self._baudrate = baudrate
        self._ser = serial.Serial(port) if baudrate is None else serial.Serial(port, baudrate)
        self._state = JediParsingStates.LookingForHeader
        self._in_payload = []
        self._out_payload = []

        # Payload reading variables.
        self._N = 0
        self._cnt = 0
        self._chksum = 0

        # thread related variables.
        self._abort = False
        self._sleeping = False
        # self.setDaemon(False)
    
    @property
    def sleeping(self):
        """ Returns if the thread is sleeping.
        """
        return self._sleeping
    
    def is_open(self):
        """Returns if the serial port is open.
        """
        return self._port if self._ser.is_open else ""

    def send_message(self, outbytes):
        _outpayload = [0xAA, 0xAA, len(outbytes)+1, *outbytes]
        _outpayload.append(sum(_outpayload) % 256)
        # Send payload.
        if _OUTDEBUG:
            sys.stdout.write("\n Out data: ")
            for _elem in _outpayload:
                sys.stdout.write(f"{_elem} ")
        self._ser.write(bytearray(_outpayload))

    def run(self):
        """
        Thread operation.
        """
        self._state = JediParsingStates.LookingForHeader
        while True and self._ser.isOpen():
            # check if the currently paused
            if self._sleeping:
                # wait till the thread is un-paused.
                continue

            # abort?
            if self._abort is True:
                return

            self._read_handle_data()

    def sleep(self):
        """
        Puts the current thread in a paused state.
        """
        # with self.state:
        self._sleeping = True

    def wakeup(self):
        """
        Wake up a paused thread.
        """
        self._sleeping = False

    def abort(self):
        """
        Aborts the current thread.
        """
        self._abort = True
        self._ser.close()
        if self._sleeping:
            self.wakeup()

    def _read_handle_data(self):
        """
        Reads and handles the received data by calling the inform function.
        """
        # Read full packets.
        if self._ser.inWaiting() and _INDEBUG:
            sys.stdout.write("\n New data: ")
        try:
            while self._ser.inWaiting():
                _byte = self._ser.read()
                if  _INDEBUG:
                    sys.stdout.write(f"{ord(_byte)} ")
                if self._state == JediParsingStates.LookingForHeader:
                    if ord(_byte) == 0xff:
                        self._state = JediParsingStates.FoundHeader1
                elif self._state == JediParsingStates.FoundHeader1:
                    if ord(_byte) == 0xff:
                        self._state = JediParsingStates.FoundHeader2
                    else:
                        self._state = JediParsingStates.LookingForHeader
                elif self._state == JediParsingStates.FoundHeader2:
                    # Payload size cannot be zero.
                    if ord(_byte) == 0:
                        self._state = JediParsingStates.LookingForHeader
                        continue
                    # Payload size is not zero.
                    self._N = ord(_byte)
                    self._cnt = 0
                    self._chksum = 255 + 255 + self._N
                    self._in_payload = [ None ] * (self._N - 1)
                    self._state = JediParsingStates.ReadingPayload
                elif self._state == JediParsingStates.ReadingPayload:
                    self._in_payload[self._cnt] = ord(_byte)
                    self._chksum += ord(_byte)
                    self._cnt += 1
                    if self._cnt == self._N - 1:
                        self._state = JediParsingStates.CheckCheckSum
                elif self._state == JediParsingStates.CheckCheckSum:
                    if self._chksum % 256 == ord(_byte):
                        self._state = JediParsingStates.FoundFullPacket
                    else:
                        self._state = JediParsingStates.LookingForHeader
                
                # Handle full packet.
                if self._state == JediParsingStates.FoundFullPacket:
                    self.newdata_signal.emit(self._in_payload)
                    self._state = JediParsingStates.LookingForHeader
        except serial.serialutil.SerialException:
            return


if __name__ == '__main__':
    jedireader = JediComm("COM4")
    jedireader.start()
    time.sleep(10)
    jedireader.abort()