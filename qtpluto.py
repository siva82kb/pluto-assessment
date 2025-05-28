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
        self._packetnumber = 0
        self._runtime = 0.0
        self.currsensordata = []
        # Other variables.
        self._preverrstatus = 0
        self._currerrstatus = 0
        # framerate related stuff
        self._currt = None
        self._prevt = None
        self._deltimes = []
        # Version and device name
        self._version = ""
        self._devname = ""
        self._compliedate = ""
        # Packet decoding functions.
        self._packet_type_handlers = {
            pdef.OutDataType["SENSORSTREAM"]: self._handle_stream,
            pdef.OutDataType["DIAGNOSTICS"]: self._handle_stream,
            pdef.OutDataType["VERSION"]: self._handle_version,
        }

        # Call back for newdata_signal
        self.dev.newdata_signal.connect(self._callback_newdata)

        # start the communication
        self.dev.start()

    @property
    def devname(self):
        return self._devname
    
    @property
    def compliedate(self):
        return self._compliedate
    
    @property
    def version(self):
        return self._version

    @property
    def systime(self):
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
    def desired(self):
        return self.currsensordata[4] if len(self.currsensordata) > 0 else None
    
    @property
    def err(self):
        return self.currsensordata[5] if len(self.currsensordata) > 4 else None
    
    @property
    def errdiff(self):
        return self.currsensordata[6] if len(self.currsensordata) > 5 else None
    
    @property
    def errsum(self):
        return self.currsensordata[7] if len(self.currsensordata) > 6 else None
    
    @property
    def currt(self):
        return self._currt

    @property
    def prevt(self):
        return self._prevt
    
    @property
    def packetnumber(self):
        return self.currstatedata[4] if len(self.currstatedata) > 0 else None
    
    @property
    def controlbound(self):
        return (1.0 * self.currstatedata[6] /255) if len(self.currstatedata) > 0 else None
    
    @property
    def controldir(self):
        return self.currstatedata[7] if len(self.currstatedata) > 0 else None
    
    @property
    def controlgain(self):
        return (
            (pdef.PlutoMaxControlGain - pdef.PlutoMinControlGain) * (self.currstatedata[8] / 255.0) + pdef.PlutoMinControlGain
            if len(self.currstatedata) > 0 
            else None
        )
    
    @property
    def button(self):
        return self.currstatedata[9] if len(self.currstatedata) > 0 else None

    def delt(self):
        return self._deltimes[-1] if len(self._deltimes) > 0 else 0
    
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
        # System time - 0
        self.currstatedata = [datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]
        # status - 1
        self.currstatedata.append(newdata[0])
        # error - 2
        self.currstatedata.append(255 * newdata[2] + newdata[1])
        # actuated - 3
        self.currstatedata.append(newdata[3])
        
        # Decode according to the datatype.
        self._packet_type_handlers[self.datatype](newdata)
    
    def _handle_stream(self, newdata):
        """
        Function to handle SENSORSTREAM and DIAGNOSTICS data.
        """
        # Packet number - 4 
        self.currstatedata.append(255 * newdata[5] + newdata[4])

        # Run time - 5
        self.currstatedata.append(struct.unpack('L', bytes(newdata[6:10]))[0])

        # Robot sensor data. This depends on the datatype.
        N = pdef.PlutoSensorDataNumber[pdef.get_name(pdef.OutDataType, self.datatype)]

        # pluto sensor data
        self.currsensordata = [
            struct.unpack('f', bytes(newdata[i:i+4]))[0]
            for i in range(10, 10 + N * 4, 4)
        ]

        # Control bound - 6
        self.currstatedata.append(newdata[10 + N * 4])
        # Control direction - 7
        self.currstatedata.append(newdata[10 + N * 4 + 1])
        # # Control gain - 8
        self.currstatedata.append(newdata[10 + N * 4 + 2])
        # PLUTO button - 9
        self.currstatedata.append(newdata[10 + N * 4 + 3])
        
        # Update frame rate related data.
        self._currt = self.currstatedata[5] * 1e-3
        if self.prevt is not None:
            self._deltimes.append(self._currt - self._prevt)
            if len(self._deltimes) > FR_WINDOW_N:
                self._deltimes.pop(0)
        self._prevt = self._currt
        
        # Emit newdata signal for other listeners
        self.newdata.emit()

        # Check and verify button events.
        if len(self.currstatedata) > 0 and len(self.prevstatedata) > 4:    
            if self.prevstatedata[9] == 1.0 and self.currstatedata[9] == 0.0:
                self.btnpressed.emit()
            if self.prevstatedata[9] == 0.0 and self.currstatedata[9] == 1.0:
                self.btnreleased.emit()
    
    def _handle_version(self, newdata):
        """
        Function to handle VERSION data.
        """
        self._devname, self._version, self._compliedate = bytes(newdata[4:]).decode('ascii').split(",")

    def close(self):
        """Function to close the connection.
        """
        if self.dev is not None and self.dev.isRunning():
            self.dev.abort()
            self.dev.quit()
            self.dev.wait()
    
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
    
    def set_control_target(self, target, target0=None, t0=None, dur=None):
        """Function to set the contoller target position.
        """
        if not self.is_connected():
            return
        # Set default values
        target0 = target0 if target0 is not None else self.target
        t0 = t0 if t0 is not None else 0.0
        dur = dur if dur is not None else 0.0
        _payload = [pdef.InDataType["SET_CONTROL_TARGET"]]
        _payload += list(struct.pack('f', target0))
        _payload += list(struct.pack('f', t0))
        _payload += list(struct.pack('f', target))
        _payload += list(struct.pack('f', dur))
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
    
    def get_version(self):
        """Get the version of the device.
        """
        _payload = [pdef.InDataType["GET_VERSION"]]
        self.dev.send_message(_payload)
    
    def set_control_bound(self, bound):
        """Set the control bound.
        """
        if not self.is_connected():
            return
        # Make sure the bound is between 0 and 1.
        bound = max(pdef.PlutoMinControlBound, min(bound, pdef.PlutoMaxControlBound))
        _payload = [pdef.InDataType["SET_CONTROL_BOUND"]]
        _payload.append(int(bound * 255))
        self.dev.send_message(_payload)
    
    def set_control_dir(self, dir):
        """Set the control direction.
        """
        if not self.is_connected():
            return
        # Make sure the direction is either 0 or +/-1.
        if dir not in [-1, 0, 1]:
            return
        _payload = [pdef.InDataType["SET_CONTROL_DIR"]]
        _payload.append(struct.pack('b', dir)[0])
        self.dev.send_message(_payload)
    
    def set_control_gain(self, gain):
        """Set the control gain.
        """
        if not self.is_connected():
            return
        # Limit the gain to the max and min value.
        gain = max(pdef.PlutoMinControlGain, min(gain, pdef.PlutoMaxControlGain))
        _payload = [pdef.InDataType["SET_CONTROL_GAIN"]]
        _payload.append(int((gain - pdef.PlutoMinControlGain) * 255 / (pdef.PlutoMaxControlGain - pdef.PlutoMinControlGain)))
        self.dev.send_message(_payload)
    
    def send_heartbeat(self):
        """Send a heartbeat signal to the device.
        """
        if not self.is_connected():
            return
        _payload = [pdef.InDataType["HEARTBEAT"]]
        self.dev.send_message(_payload)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    from qtjedi import JediComm
    app = QApplication(sys.argv)
    pluto = QtPluto(port="COM12")
    pluto.stop_sensorstream()
    pluto.get_version()
    pluto.send_heartbeat()
    pluto.start_sensorstream()
    app.exec_()