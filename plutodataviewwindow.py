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
    QtWidgets,)
from enum import Enum

import plutodefs as pdef
from ui_plutodataview import Ui_DevDataWindow


class PlutoDataViewWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO data viewer window.
    """
    def __init__(self, parent=None, plutodev: QtPluto=None, pos: tuple[int]=None):
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
        if len(self.pluto.currdata) == 0:
            self.ui.textDevData.setText("No data available.")
            return
        # New data available. Format and display
        _dispdata = [
            f"PLUTO Data [fr: {self.pluto.framerate():4.1f}Hz]",
            "----------",
            f"Time    : {self.pluto.currdata[0]}",
            f"Status  : {pdef.OutDataType[self.pluto.datatype]} | {pdef.ControlType[self.pluto.controltype]} | {pdef.CalibrationStatus[self.pluto.calibration]}",
            f"Error   : {pdef.ErrorTypes[self.pluto.error]}",
            f"Mech    : {pdef.Mehcanisms[self.pluto.mechanism]:<5s} | Calib   : {pdef.CalibrationStatus[self.pluto.calibration]}",
            f"Actd    : {self.pluto.actuated}",
        ]
        _dispdata += [
            f"Angle   : {self.pluto.angle:-07.2f}deg"
            + f" [{self.pluto.hocdisp:05.2f}cm]" if self.pluto.calibration == 1 else ""
        ]
        _dispdata += [
            f"Torque  : {self.pluto.torque:3.1f}Nm",
            f"fb Ctrl : {self.pluto.feedbackcontrol:3.1f}",
            f"ff Ctrl : {self.pluto.feedforwardcontrol:3.1f}",
            f"Tgt Pos : {self.pluto.desiredposition:3.1f}",
            f"Tgt Torq: {self.pluto.desiredtorque:3.1f}",
            f"Button  : {self.pluto.button}",
        ]
        self.ui.textDevData.setText('\n'.join(_dispdata))
    
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
    pdataview = PlutoDataViewWindow(plutodev=plutodev)
    pdataview.show()
    sys.exit(app.exec_())
