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
        if self._mode == "DIAGNOSTICS":
            self._pluto.set_diagnostic_mode()
        else:
            self._pluto.start_sensorstream()

        # Display counter
        self._dispcount = 0

        # Attach callbacks
        self.pluto.newdata.connect(self._callback_pluto_newdata)

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
            f"Time    : {self.pluto.time}"
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
                f"Err     : {self.pluto.error:3.1f}",
                f"ErrDiff : {self.pluto.errordiff:3.1f}",
                f"ErrSum  : {self.pluto.errorsum:3.1f}",
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


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM4")
    pdataview = PlutoDataViewWindow(plutodev=plutodev,
                                    mode="DIAGNOSTICS")
    pdataview.show()
    sys.exit(app.exec_())
