"""
Module for handling the operation of the PLUTO calibration window.

Author: Sivakumar Balasubramanian
Date: 02 August 2024
Email: siva82kb@gmail.com
"""


import sys
import numpy as np
from datetime import datetime as dt

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,)
from PyQt5.QtCore import QTimer
from enum import Enum

import plutodefs as pdef
from plutodataviewwindow import PlutoDataViewWindow
from ui_plutocalib import Ui_CalibrationWindow

# Some timing constants
CALIB_DUMMY_TIME = 0.25         # Time to wait for dummy calibration
HIT_LIMIT_TIME = 1.50           # Time to wait to hit the limit
CALIB_TIME = 1.00               # Calibrate

# Limit hitting torques
LIMIT_HIT_TORQUE = 0.08         # Torque to hit the limit
LIMIT_HIT_TORQUE_HOC = 0.20     # Torque to hit the limit


class PlutoCalibStates(Enum):
    # WAIT_FOR_ZERO_SET = 0
    # WAIT_FOR_ROM_SET = 1
    # WAIT_FOR_CLOSE = 2
    # CALIB_DONE = 3
    # CALIB_ERROR = 4
    WAIT_FOR_START = 0
    DUMMY_CALIB_START = 1
    DUMMY_CALIB_END = 2
    HIT_CCWISE_LIMIT = 4
    SET_CALIB_START = 5
    HIT_CWISE_LIMIT = 6
    CHECK_CALIB_ANGLE = 7
    SET_CALIB_END = 8
    CALIB_DONE = 9
    CALIB_ERROR = 10
    EXIT = 11


class PlutoCalibrationStateMachine():
    def __init__(self, plutodev: QtPluto, mech: str="NONE"):
        self._state = PlutoCalibStates.WAIT_FOR_START
        self._pluto = plutodev
        self._stateactions = {
            PlutoCalibStates.WAIT_FOR_START: self._calib_start,
            PlutoCalibStates.DUMMY_CALIB_START: self._dummy_calib_start,
            PlutoCalibStates.DUMMY_CALIB_END: self._dummy_calib_end,
            PlutoCalibStates.HIT_CCWISE_LIMIT: self._hit_ccwise_limit,
            PlutoCalibStates.SET_CALIB_START: self._set_calib_start,
            PlutoCalibStates.HIT_CWISE_LIMIT: self._hit_cwise_limit,
            PlutoCalibStates.CHECK_CALIB_ANGLE: self._check_calib_angle,
            PlutoCalibStates.SET_CALIB_END: self._calib_end,
            PlutoCalibStates.CALIB_ERROR: self._calib_error,
            PlutoCalibStates.CALIB_DONE: self._calib_done
        }
        self._mech = mech
        self._state_t0 = 0
        # Set control mode to TORQUE
        self._pluto.set_control_type("TORQUE")
    
    @property
    def state(self):
        return self._state

    def run_statemachine(self, event):
        """Execute the state machine depending on the given even that has occured.
        """
        print(f"Calib SM: State={self._state}, Event={event}, Time={self._pluto.currt - self._state_t0:0.2f}s")
        self._stateactions[self._state](event)
    
    def _calib_start(self, event):
        # Check if the button release event has happened.
        if event == pdef.PlutoEvents.RELEASED:
            self._pluto.calibrate_start(self._mech)
            self._state = PlutoCalibStates.DUMMY_CALIB_START
            self._state_t0 = self._pluto.currt
            return
    
    def _dummy_calib_start(self, event):
        # Set a dummy calibration to start with.
        if (self._pluto.currt - self._state_t0) > CALIB_DUMMY_TIME:
            self._pluto.calibrate_end(self._mech)
            self._state = PlutoCalibStates.DUMMY_CALIB_END
            self._state_t0 = self._pluto.currt
        return

    def _dummy_calib_end(self, event):
        # Wait for some time after dummy calib end.
        if (self._pluto.currt - self._state_t0) > CALIB_DUMMY_TIME:
            # Move to torque control mode
            self._pluto.set_control_type("TORQUE")
            self._state = PlutoCalibStates.HIT_CCWISE_LIMIT
            self._state_t0 = self._pluto.currt
        return

    def _hit_ccwise_limit(self, event):
        # Set a torque to move to CCWISE direction
        if (self._pluto.currt - self._state_t0) > CALIB_DUMMY_TIME:
            self._pluto.set_control_target(
                LIMIT_HIT_TORQUE_HOC if self._mech == "HOC" else -LIMIT_HIT_TORQUE
            )
            self._state_t0 = self._pluto.currt
            self._state = PlutoCalibStates.SET_CALIB_START
        return

    def _set_calib_start(self, event):
        # Set a torque to move to CCWISE direction
        if (self._pluto.currt - self._state_t0) > HIT_LIMIT_TIME:
            self._pluto.calibrate_start(self._mech)
            self._state_t0 = self._pluto.currt
            self._state = PlutoCalibStates.HIT_CWISE_LIMIT
        return

    def _hit_cwise_limit(self, event):
        # Set a torque to move to CCWISE direction
        if (self._pluto.currt - self._state_t0) > CALIB_DUMMY_TIME:
            self._pluto.set_control_target(
                -LIMIT_HIT_TORQUE_HOC if self._mech == "HOC" else LIMIT_HIT_TORQUE
            )
            self._state_t0 = self._pluto.currt
            self._state = PlutoCalibStates.CHECK_CALIB_ANGLE
        return
    
    def _check_calib_angle(self, event):
        if (self._pluto.currt - self._state_t0) > HIT_LIMIT_TIME:
            _angval = self._pluto.angle + pdef.PlutoAngleOffset[self._mech]
            if ((abs(_angval) < (0.9 * pdef.PlutoAngleRanges[self._mech]))
                or (abs(_angval) > (1.1 * pdef.PlutoAngleRanges[self._mech]))):
                # Calibration error
                self._state = PlutoCalibStates.CALIB_ERROR
            else:
                self._pluto.calibrate_end(self._mech)
                self._state_t0 = self._pluto.currt
                self._state = PlutoCalibStates.SET_CALIB_END
        return

    def _calib_end(self, event):
        # Set a torque to move to CCWISE direction
        if (self._pluto.currt - self._state_t0) > CALIB_TIME:
            self._pluto.set_control_type("NONE")
            self._state = PlutoCalibStates.CALIB_DONE
            return

    def _calib_error(self, event):
        self._pluto.calibrate_start("NOMECH")
        self._pluto.calibrate_end("NOMECH")
        if event == pdef.PlutoEvents.RELEASED:
            # Calibration all done.
            self._state = PlutoCalibStates.EXIT
        pass

    def _calib_done(self, event):
        if event == pdef.PlutoEvents.RELEASED:
            self._state = PlutoCalibStates.EXIT


class PlutoCalibrationWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO calibration window.
    """
    def __init__(self, parent=None, plutodev: QtPluto=None, limb=None, mechanism: str=None, 
                 modal=False, dataviewer=False, onclosecb=None, heartbeat=False):
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
        self._limb = limb if limb else "NOLIMB"
        self._mechanism = mechanism

        # Heartbeat timer
        self._heartbeat = heartbeat
        if self._heartbeat:
            self.heartbeattimer = QTimer()
            self.heartbeattimer.timeout.connect(lambda: self.pluto.send_heartbeat())
            self.heartbeattimer.start(500)

        # Set to NOMECH to start with
        self.pluto.send_heartbeat()
        self._pluto.set_limb(self._limb.upper())
        self._pluto.calibrate_start("NOMECH")
        # Pause for 0.5sec
        QTimer.singleShot(500, lambda: None) 

        # Initialize the state machine.
        self._smachine = PlutoCalibrationStateMachine(self._pluto, mech=self._mechanism)

        # Attach callbacks
        self._attach_pluto_callbacks()

        # Update UI.
        self.update_ui()
        # Set label for position display.
        if self._mechanism == "HOC":
            self.ui.lblPositionTitle.setText("Hand Aperture:")
        else:
            self.ui.lblPositionTitle.setText("Joint Position:")
        self.ui.lblInstruction.setText(f"Calibration for {self._mechanism} mechanism for {self._limb} limb.")

        # Open the PLUTO data viewer window for sanity
        if dataviewer:
            # Open the device data viewer by default.
            self._open_devdata_viewer()

        # Set the callback when the window is closed.
        self.on_close_callback = onclosecb

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
        if self._smachine.state == PlutoCalibStates.WAIT_FOR_START:
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText("Press the PLUTO button start calibration.")
        elif (self._smachine.state == PlutoCalibStates.DUMMY_CALIB_START):
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText("Dummy Calibration Started.")
        elif (self._smachine.state == PlutoCalibStates.DUMMY_CALIB_END):
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText(f"Dummy Calibration Done [Mechanism = {pdef.get_name(pdef.Mechanisms, self.pluto.mechanism)}].")
        elif (self._smachine.state == PlutoCalibStates.HIT_CCWISE_LIMIT):
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText(f"Going to CCW Limit [{self._pluto.angle:4.2f}].")
        elif (self._smachine.state == PlutoCalibStates.SET_CALIB_START):
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText(f"Setting Calibration Start [{self._pluto.angle:4.2f}].")
        elif (self._smachine.state == PlutoCalibStates.HIT_CWISE_LIMIT):
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText(f"Going to CW Limit [{self._pluto.angle:4.2f}].")
        elif (self._smachine.state == PlutoCalibStates.CHECK_CALIB_ANGLE):
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText(f"Checking Angle Range [{self._pluto.angle:4.2f}].")
        elif (self._smachine.state == PlutoCalibStates.CHECK_CALIB_ANGLE):
            self.ui.lblCalibStatus.setText("Not done.")
            self.ui.lblPositionDisplay.setText("- NA- ")
            self.ui.lblInstruction2.setText(f"Checking Angle Range [{self._pluto.angle:4.2f}].")
        elif (self._smachine.state == PlutoCalibStates.CALIB_DONE):
            self.ui.lblCalibStatus.setText("Calibration done.")
            self.ui.lblPositionDisplay.setText(
                f"{self.pluto.hocdisp:5.2f}cm" if self.mechanism == "HOC"
                else f"{self.pluto.angle:5.2f}deg"
            )
            self.ui.lblInstruction2.setText(f"Press PLUTO button to exit.")
        elif self._smachine.state == PlutoCalibStates.CALIB_ERROR:
            self.ui.lblCalibStatus.setText("Error!")
            self.ui.lblInstruction2.setText("Press the PLUTO button to close window.")
        elif self._smachine.state == PlutoCalibStates.EXIT:
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
    def _attach_pluto_callbacks(self):
        self.pluto.newdata.connect(self._callback_pluto_newdata)
        self.pluto.btnreleased.connect(self._callback_pluto_btn_released)
    
    def _detach_pluto_callbacks(self):
        self.pluto.newdata.disconnect(self._callback_pluto_newdata)
        self.pluto.btnreleased.disconnect(self._callback_pluto_btn_released)
    
    def _callback_pluto_newdata(self):
        self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA
        )
        self.update_ui()

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED
        )
        self.update_ui()
    
    #
    # Close event
    #
    def closeEvent(self, event):
        # Run the callback
        if self.on_close_callback:
            self.on_close_callback(data={"done": self.pluto.calibration == pdef.CalibrationStatus["YESCALIB"]})
        # Disconnect the PLUTO callbacks.
        self._detach_pluto_callbacks()
        return super().closeEvent(event)


if __name__ == '__main__':
    import qtjedi
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM5")
    pcalib = PlutoCalibrationWindow(plutodev=plutodev, limb="LEFT", mechanism="FPS",
                                    dataviewer=True, heartbeat=True, 
                                    onclosecb=lambda data: print(dt.now()))
    pcalib.show()
    sys.exit(app.exec_())
