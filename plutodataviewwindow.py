"""
Module for handling the operation of the PLUTO data viewer window.

Author: Sivakumar Balasubramanian
Date: 04 August 2024
Email: siva82kb@gmail.com
"""


import sys
import numpy as np

from qtpluto import QtPluto

from PyQt5 import (
    QtWidgets,
)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QKeyEvent
from enum import Enum

import plutodefs as pdef
from ui_plutodataview import Ui_DevDataWindow


class PlutoDataViewWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO data viewer window.
    """
    def __init__(self, parent=None, plutodev: QtPluto=None, 
                 mode="SENSORSTREAM", pos: tuple[int]=None):
        """
        Constructor for the PlutoDataViewWindow class.
        """
        super(PlutoDataViewWindow, self).__init__(parent)
        self.ui = Ui_DevDataWindow()
        self.ui.setupUi(self)
        if pos is not None:
            self.move(*pos)
        
        # PLUTO device
        self._pluto = plutodev

        # PLUTO mode
        self._mode = mode
        # Get the version and device information
        self._pluto.get_version()
        # Pause for 0.5sec
        QTimer.singleShot(500, lambda: None) 
        if self._mode == "DIAGNOSTICS":
            self._pluto.set_diagnostic_mode()
        else:
            self._pluto.start_sensorstream()

        # Display counter
        self._dispcount = 0

        # Attach callbacks
        self.pluto.newdata.connect(self._callback_pluto_newdata)
        # self.pluto.btnreleased.connect(self._callback_pluto_button_released)
        # self.pluto.btnpressed.connect(self._callback_pluto_button_pressed)

        # Heartbeat timer
        self.heartbeattimer = QTimer()
        self.heartbeattimer.timeout.connect(lambda: self.pluto.send_heartbeat())
        self.heartbeattimer.start(500)

        # Update UI.
        self.update_ui()

    @property
    def pluto(self):
        return self._pluto
    
    #
    # Update UI
    #
    def update_ui(self):
        # Check if new data is available
        if self.pluto.is_data_available() is False:
            self.ui.textDevData.setText("No data available.")
            return
        # New data available. Format and display
        _dispdata = [
            f"PLUTO Data [fr: {self.pluto.framerate():4.1f}Hz]",
            "----------",
            f"Dev Name: {self.pluto.devname}",
            f"F/W Ver : {self.pluto.version} | Compile Date: {self.pluto.compliedate}",
            f"Time    : {self.pluto.systime}",
            f"Dev Time: {self.pluto.currt:6.3f}s | Pack No : {self.pluto.packetnumber:06d}",
        ]
        _statusstr = ' | '.join((pdef.get_name(pdef.OutDataType, self.pluto.datatype),
                                 pdef.get_name(pdef.ControlType, self.pluto.controltype),
                                 pdef.get_name(pdef.CalibrationStatus, self.pluto.calibration)))
        _dispdata += [
            f"Status  : {_statusstr}",
            f"Error   : {pdef.get_name(pdef.ErrorTypes, self.pluto.error)}",
            f"Mech    : {pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism):<6s} | Calib   : {pdef.get_name(pdef.CalibrationStatus, self.pluto.calibration)}",
            f"Actd    : {self.pluto.actuated:<6d} | Button  : {self.pluto.button}",
            ""
        ]
        _dispdata += [
            "~ SENSOR DATA ~",
            f"Angle   : {self.pluto.angle:-07.2f}deg"
            + (f" [{self.pluto.hocdisp:05.2f}cm]" if self.pluto.calibration == 1 else "")
        ]
        _dispdata += [
            f"Torque  : {self.pluto.torque:3.1f}Nm",
            f"Control : {self.pluto.control:3.1f}",
            f"Target  : {self.pluto.target:3.1f}",
        ]
        # Check if in DIAGNOSTICS mode.
        if pdef.get_name(pdef.OutDataType, self.pluto.datatype) == "DIAGNOSTICS":
            _dispdata += [
                f"Err     : {self.pluto.err:3.1f}",
                f"ErrDiff : {self.pluto.errdiff:3.1f}",
                f"ErrSum  : {self.pluto.errsum:3.1f}",
            ]
        # Control bound, dir and gain
        _dispdata += [
            f"C Bound : {self.pluto.controlbound:1.2f}",
            f"C Dir   : {self.pluto.controldir}",
            f"C Gain  : {self.pluto.controlgain:02.2f}",
        ]
        self.ui.textDevData.setText('\n'.join(_dispdata))
    
    #
    # Key release event
    #
    def keyReleaseEvent(self, event):
        if isinstance(event, QKeyEvent):
            key_text = event.text()
            print(f"Key Released: {key_text}")

    #
    # Signal Callbacks
    # ss
    def _callback_pluto_newdata(self):
        self._dispcount += 1
        self._dispcount %= 10
        if self._dispcount == 0:
            self.update_ui()
    
    def _callback_pluto_button_released(self):
        print("Button released.")
    
    def _callback_pluto_button_pressed(self):
        print("Button pressed.")

    #
    # Close event
    #
    def closeEvent(self, event):
        try:
            self.pluto.set_control_type("NONE")
            self.pluto.close()
        except Exception as e:
            print(f"Error during close: {e}")
        return super().closeEvent(event)

    
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM12")
    pdataview = PlutoDataViewWindow(plutodev=plutodev,
                                    mode="DIAGNOSTICS")
    pdataview.show()
    sys.exit(app.exec_())
