"""
Module implementing a QObject for abstracing PLUTO which uses the qtjedi
to connect to the device, unpack data, and send/receive signals.

Author: Sivakumar Balasubramanian
Date: 24 July 2024
Email: siva82kb@gmail.com
"""

from PyQt5.QtCore import QObject, pyqtSignal
from qtjedi import JediComm
from collections import deque
from datetime import datetime
import struct

import plutodefs as pdef

# Frame rate estimation window
FR_WINDOW_N = 100
class QtPluto(QObject):
    """
    Class to handle PLUTO IO operations. 
    """
    newdata = pyqtSignal()
    btnpressed = pyqtSignal()
    btnreleased = pyqtSignal()
    datanames = (
        "time",
        "status",
        "error",
        "actuated",
        "angle",
        "torque",
        "control",
        "desired",
        "button"
    )

    def __init__(self, port=None, baudrate=115200) -> None:
        super().__init__()
        self.dev = JediComm(port, baudrate)
        # Upacked data from PLUTO with time stamp.
        self.currstatedata = []
        self.prevstatedata = []
        self.currsensordata = []
        # framerate related stuff
        self._currt = None
        self._prevt = None
        self._deltimes = []

        # Call back for newdata_signal
        self.dev.newdata_signal.connect(self._callback_newdata)

        # start the communication
        self.dev.start()

    @property
    def time(self):
        return self.currstatedata[0] if len(self.currstatedata) > 0 else None
    
    @property
    def status(self):
        return self.currstatedata[1] if len(self.currstatedata) > 0 else None
    
    @property
    def datatype(self):
        return self.status >> 4 if len(self.currstatedata) > 0 else None
    
    @property
    def controltype(self):
        return (self.status & 0x0E) >> 1 if len(self.currstatedata) > 0 else None
    
    @property
    def calibration(self):
        return self.status & 0x01 if len(self.currstatedata) > 0 else None

    @property
    def error(self):
        return self.currstatedata[2] if len(self.currstatedata) > 0 else None
    
    @property
    def mechanism(self):
        return self.currstatedata[3] >> 4 if len(self.currstatedata) > 0 else None
    
    @property
    def actuated(self):
        return self.currstatedata[3] & 0x01 if len(self.currstatedata) > 0 else None
    
    @property
    def button(self):
        return self.currstatedata[4] if len(self.currstatedata) > 0 else None
    
    @property
    def angle(self):
        return self.currsensordata[0] if len(self.currsensordata) > 0 else None
    
    @property
    def hocdisp(self):
        return pdef.HOCScale * abs(self.currsensordata[0]) if len(self.currsensordata) > 0 else None
    
    @property
    def torque(self):
        return self.currsensordata[1] if len(self.currsensordata) > 0 else None
    
    @property
    def control(self):
        return self.currsensordata[2] if len(self.currsensordata) > 0 else None
    
    @property
    def target(self):
        return self.currsensordata[3] if len(self.currsensordata) > 0 else None
    
    @property
    def error(self):
        return self.currsensordata[4] if len(self.currsensordata) > 4 else None
    
    @property
    def errordiff(self):
        return self.currsensordata[5] if len(self.currsensordata) > 5 else None
    
    @property
    def errorsum(self):
        return self.currsensordata[6] if len(self.currsensordata) > 6 else None
    
    def framerate(self):
        return FR_WINDOW_N / sum(self._deltimes) if sum(self._deltimes) != 0 else 0.0
 
    def is_connected(self):
        return self.dev.is_open()
    
    def is_data_available(self):
        return len(self.currstatedata) != 0

    def _callback_newdata(self, newdata):
        """
        Handles newdata packect recevied through the COM port.
        """
        # Store previous data
        self.prevstatedata = self.currstatedata
        # Unpack and update current data
        self._currt = datetime.now()
        self.currstatedata = [self._currt.strftime('%Y-%m-%d %H:%M:%S.%f')]
        # status
        self.currstatedata.append(newdata[0])
        # error
        self.currstatedata.append(255 * newdata[2] + newdata[1])
        # actuated
        self.currstatedata.append(newdata[3])
        # Robot sensor data. This depends on the datatype.
        N = pdef.PlutoSensorDataNumber[pdef.get_name(pdef.OutDataType, self.datatype)]
        # pluto button
        self.currstatedata.append(newdata[(N + 1) * 4])

        # pluto sensor data
        self.currsensordata = [
            struct.unpack('f', bytes(newdata[i:i+4]))[0]
            for i in range(4, (N + 1) * 4, 4)
        ]

        # Update frame rate related data.
        if self._prevt is not None:
            _delt = (self._currt - self._prevt).microseconds * 1e-6
            self._deltimes.append(_delt)
            if len(self._deltimes) > FR_WINDOW_N:
                self._deltimes.pop(0)
        self._prevt = self._currt
        
        # Emit newdata signal for other listeners
        self.newdata.emit()
        
        # Check and verify button events.
        if len(self.currstatedata) > 0 and len(self.prevstatedata) > 0:    
            if self.prevstatedata[4] == 1.0 and self.currstatedata[4] == 0.0:
                self.btnpressed.emit()
            if self.prevstatedata[4] == 0.0 and self.currstatedata[4] == 1.0:
                self.btnreleased.emit()

    def calibrate(self, mech):
        """Function to set the encoder calibration.
        """
        if not self.is_connected():
            return
        self.dev.send_message([
            pdef.InDataType["CALIBRATE"],
            pdef.Mehcanisms[mech]
        ])
    
    def set_control_type(self, control):
        """Function to set the control type.
        """
        if not self.is_connected():
            return
        _payload = [pdef.InDataType["SET_CONTROL_TYPE"],
                    pdef.ControlType[control]]
        self.dev.send_message(_payload)
    
    def set_control_target(self, target):
        """Function to set the contoller target position.
        """
        if not self.is_connected():
            return
        _payload = [pdef.InDataType["SET_CONTROL_TARGET"]]
        _payload += list(struct.pack('f', target))
        self.dev.send_message(_payload)

    def start_sensorstream(self):
        """Starts sensor stream.
        """
        _payload = [pdef.InDataType["START_STREAM"]]
        self.dev.send_message(_payload)
    
    def stop_sensorstream(self):
        """Stop sensor stream.
        """
        _payload = [pdef.InDataType["STOP_STREAM"]]
        self.dev.send_message(_payload)
    
    def set_diagnostic_mode(self):
        """Sets the device in the diagnostics mode.
        """
        _payload = [pdef.InDataType["SET_DIAGNOSTICS"]]
        self.dev.send_message(_payload)
