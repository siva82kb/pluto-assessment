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
        self.currdata = []
        self.prevdata = []
        # framerate related stuff
        self._currt = None
        self._prevt = None
        self._deltimes = []

        # Call back for newdata_signal
        self.dev.newdata_signal.connect(self._callback_newdata)

        # start the communication
        self.dev.start()

    @property
    def status(self):
        return self.currdata[1] if len(self.currdata) > 0 else None
    
    @property
    def datatype(self):
        return self.status >> 4 if len(self.currdata) > 0 else None
    
    @property
    def controltype(self):
        return (self.status & 0x0E) >> 1 if len(self.currdata) > 0 else None
    
    @property
    def calibration(self):
        return self.status & 0x01 if len(self.currdata) > 0 else None

    @property
    def error(self):
        return self.currdata[2] if len(self.currdata) > 0 else None
    
    @property
    def mechanism(self):
        return self.currdata[3] >> 4 if len(self.currdata) > 0 else None
    
    @property
    def actuated(self):
        return self.currdata[3] & 0x01 if len(self.currdata) > 0 else None
    
    @property
    def angle(self):
        return self.currdata[4] if len(self.currdata) > 0 else None
    
    @property
    def hocdisp(self):
        return pdef.HOCScale * abs(self.currdata[4]) if len(self.currdata) > 0 else None
    
    @property
    def torque(self):
        return self.currdata[5] if len(self.currdata) > 0 else None
    
    @property
    def feedbackcontrol(self):
        return self.currdata[6] if len(self.currdata) > 0 else None
    
    @property
    def feedforwardcontrol(self):
        return self.currdata[7] if len(self.currdata) > 0 else None
    
    @property
    def desiredposition(self):
        return self.currdata[8] if len(self.currdata) > 0 else None
    
    @property
    def desiredtorque(self):
        return self.currdata[9] if len(self.currdata) > 0 else None
    
    @property
    def button(self):
        return self.currdata[10] if len(self.currdata) > 0 else None

    def framerate(self):
        return FR_WINDOW_N / sum(self._deltimes) if sum(self._deltimes) != 0 else 0.0
 
    def is_connected(self):
        return self.dev.is_open()

    def _callback_newdata(self, newdata):
        """
        Handles newdata packect recevied through the COM port.
        """
        # Store previous data
        self.prevdata = self.currdata
        # Unpack and update current data
        self._currt = datetime.now()
        self.currdata = [self._currt.strftime('%Y-%m-%d %H:%M:%S.%f')]
        # status
        self.currdata.append(newdata[0])
        # error
        self.currdata.append(255 * newdata[2] + newdata[1])
        # actuated
        self.currdata.append(newdata[3])
        # Robot sensor data
        for i in range(4, 28, 4):
            self.currdata.append(struct.unpack('f', bytes(newdata[i:i+4]))[0])
        # pluto button
        self.currdata.append(newdata[28])
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
        if len(self.currdata) > 0 and len(self.prevdata) > 0:    
            if self.prevdata[10] == 1.0 and self.currdata[10] == 0.0:
                self.btnpressed.emit()
            if self.prevdata[10] == 0.0 and self.currdata[10] == 1.0:
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
    
    def set_position_target(self, target):
        """Function to set the position controller's target position.
        """
        if not self.is_connected():
            return
        _payload = [pdef.InDataType["SET_POSITION_TGT"]]
        _payload += list(struct.pack('f', target))
        self.dev.send_message(_payload)
    
    def set_feedforward_torque(self, target):
        """Function to set the feedforward torque.
        """
        if not self.is_connected():
            return
        _payload = [pdef.InDataType["SET_TORQUE_TGT"]]
        _payload += list(struct.pack('f', target))
        self.dev.send_message(_payload)
