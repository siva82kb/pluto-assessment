"""
Module for handling the operation of the PLUTO calibration window.

Author: Sivakumar Balasubramanian
Date: 02 August 2024
Email: siva82kb@gmail.com
"""


import sys
import numpy as np

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,)
from enum import Enum

import plutodefs as pdef
from plutodataviewwindow import PlutoDataViewWindow
from ui_plutocalib import Ui_CalibrationWindow


class PlutoCalibStates(Enum):
    WAIT_FOR_ZERO_SET = 0
    WAIT_FOR_ROM_SET = 1
    WAIT_FOR_CLOSE = 2
    CALIB_DONE = 3
    CALIB_ERROR = 4


class PlutoCalibrationStateMachine():
    def __init__(self, plutodev):
        self._state = PlutoCalibStates.WAIT_FOR_ZERO_SET
        self._pluto = plutodev
        self._stateactions = {
            PlutoCalibStates.WAIT_FOR_ZERO_SET: self._zero_set,
            PlutoCalibStates.WAIT_FOR_ROM_SET: self._rom_set,
            PlutoCalibStates.WAIT_FOR_CLOSE: self._close,
            PlutoCalibStates.CALIB_ERROR: self._calib_error,
            PlutoCalibStates.CALIB_DONE: self._calib_done
        }
    
    @property
    def state(self):
        return self._state

    def run_statemachine(self, event, mech):
        """Execute the state machine depending on the given even that has occured.
        """
        self._stateactions[self._state](event, mech)
    
    def _zero_set(self, event, mech):
        # Check if the button release event has happened.
        if event == pdef.PlutoEvents.RELEASED:
            # Send the calibration command to the device.
            self._pluto.calibrate(mech)
            return
        # Check of the calibration is done.
        if (event == pdef.PlutoEvents.NEWDATA
            and self._pluto.calibration == pdef.CalibrationStatus["YESCALIB"]):
            self._state = PlutoCalibStates.WAIT_FOR_ROM_SET
    
    def _rom_set(self, event, mech):
        # Check of the calibration is done.
        if self._pluto.calibration == pdef.CalibrationStatus["NOCALIB"]:
            self._state = PlutoCalibStates.WAIT_FOR_ZERO_SET
            return
        # Check if the button release event has happened.
        if event == pdef.PlutoEvents.RELEASED:
            # Check if the ROM is acceptable.
            _romcheck = (np.abs(self._pluto.angle) >= 0.9 * pdef.PlutoAngleRanges[mech]
                         and np.abs(self._pluto.angle) <= 1.1 * pdef.PlutoAngleRanges[mech])
            if _romcheck:
                # Everything looks good. Calibration is complete.
                self._state = PlutoCalibStates.WAIT_FOR_CLOSE
            else:
                # ROM is not acceptable. Calibration Error.
                self._state = PlutoCalibStates.CALIB_ERROR
    
    def _close(self, event, mech):
        # Check if the button release event has happened.
        if event == pdef.PlutoEvents.RELEASED:
            # Calibration all done.
            self._state = PlutoCalibStates.CALIB_DONE
    
    def _calib_error(self, event, mech):
        self._pluto.calibrate("NOMECH")
        if event == pdef.PlutoEvents.RELEASED:
            # Calibration all done.
            self._state = PlutoCalibStates.CALIB_DONE

    def _calib_done(self, event, mech):
        pass


class PlutoCalibrationWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO calibration window.
    """
    def __init__(self, parent=None, plutodev: QtPluto=None, mechanism: str=None, modal=False, dataviewer=False):
        """
        Constructor for the PlutoCalibrationWindow class.
        """
        super(PlutoCalibrationWindow, self).__init__(parent)
        self.ui = Ui_CalibrationWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # PLUTO device
        self._pluto = plutodev
        self._mechanism = mechanism

        # Initialize the state machine.
        self._smachine = PlutoCalibrationStateMachine(self._pluto)

        # Set to NOMECH to start with
        self._pluto.calibrate("NOMECH")
        # self._pluto.reset_calibration("NOMECH")
        # self._pluto.reset_calibration("NOMECH")

        # Attach callbacks
        self.pluto.newdata.connect(self._callback_pluto_newdata)
        self.pluto.btnreleased.connect(self._callback_pluto_btn_released)

        # Update UI.
        self.update_ui()
        # Set label for position display.
        if self._mechanism == "HOC":
            self.ui.lblPositionTitle.setText("Hand Aperture:")
        else:
            self.ui.lblPositionTitle.setText("Joint Position:")

        # Open the PLUTO data viewer window for sanity
        if dataviewer:
            # Open the device data viewer by default.
            self._open_devdata_viewer()


    @property
    def pluto(self):
        return self._pluto
    
    @property
    def mechanism(self):
        return self._mechanism
    
    @property
    def statemachine(self):
        return self._smachine
    
    #
    # Update UI
    #
    def update_ui(self):
        # Update based on the current state of the Calib statemachine
        if self._smachine.state == PlutoCalibStates.WAIT_FOR_ZERO_SET:
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText("Press the PLUTO button set zero.")
        elif self._smachine.state == PlutoCalibStates.WAIT_FOR_ROM_SET:
            self.ui.lblCalibStatus.setText("Zero set.")
            self.ui.lblPositionDisplay.setText(
                f"{self.pluto.hocdisp:5.2f}cm" if self.mechanism == "HOC"
                else f"{self.pluto.angle:5.2f}deg"
            )
            self.ui.lblInstruction2.setText("Press the PLUTO button set ROM.")
        elif self._smachine.state == PlutoCalibStates.WAIT_FOR_CLOSE:
            self.ui.lblCalibStatus.setText("All Done!")
            self.ui.lblPositionDisplay.setText(
                f"{self.pluto.hocdisp:5.2f}cm" if self.mechanism == "HOC"
                else f"{self.pluto.angle:5.2f}deg"
            )
            self.ui.lblInstruction2.setText("Press the PLUTO button to close window.")
        elif self._smachine.state == PlutoCalibStates.CALIB_ERROR:
            self.ui.lblCalibStatus.setText("Error!")
            self.ui.lblInstruction2.setText("Press the PLUTO button to close window.")
        else:
            try:
                self._devdatawnd.close()
            except:
                pass
            self.close()
    
    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               pos=(50, 300))
        self._devdatawnd.show()
    
    #
    # Signal Callbacks
    # 
    def _callback_pluto_newdata(self):
        self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA,
            self._mechanism
        )
        self.update_ui()

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED,
            self._mechanism
        )
        self.update_ui()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM12")
    pcalib = PlutoCalibrationWindow(plutodev=plutodev, mechanism="FPS",
                                    dataviewer=True)
    pcalib.show()
    sys.exit(app.exec_())
