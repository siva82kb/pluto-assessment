"""
Module implementing the different state machines needed for using PLUTO.

Author: Sivakumar Balasubramanian
Date: 27 July 2024
Email: siva82kb@gmail.com
"""

from PyQt5.QtCore import QObject, pyqtSignal
from enum import Enum

import plutodefs as pdef


class PlutoButtonEvents(Enum):
    PRESSED = 0
    RELEASED = 1


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
        if event == PlutoButtonEvents.RELEASED:
            # Send the calibration command to the device.
            self._pluto.calibrate(mech)
            return
        # Check of the calibration is done.
        if self._pluto.calibration == pdef.get_code(pdef.CalibrationStatus, "YESCALIB"):
            self._state = PlutoCalibStates.WAIT_FOR_ROM_SET
    
    def _rom_set(self, event, mech):
        # Check of the calibration is done.
        if self._pluto.calibration == pdef.get_code(pdef.CalibrationStatus, "NOCALIB"):
            self._state = PlutoCalibStates.WAIT_FOR_ZERO_SET
            return
        # Check if the button release event has happened.
        if event == PlutoButtonEvents.RELEASED:
            # Check if the ROM is acceptable.
            _romcheck = (-self._pluto.angle >= 0.9 * pdef.PlutoAngleRanges[mech]
                         and -self._pluto.angle <= 1.1 * pdef.PlutoAngleRanges[mech])
            if _romcheck:
                # Everything looks good. Calibration is complete.
                self._state = PlutoCalibStates.WAIT_FOR_CLOSE
            else:
                # ROM is not acceptable. Calibration Error.
                self._state = PlutoCalibStates.CALIB_ERROR
    
    def _close(self, event, mech):
        # Check if the button release event has happened.
        if event == PlutoButtonEvents.RELEASED:
            # Calibration all done.
            self._state = PlutoCalibStates.CALIB_DONE
    
    def _calib_error(self, event, mech):
        self._pluto.calibrate("NOMECH")
        if event == PlutoButtonEvents.RELEASED:
            # Calibration all done.
            self._state = PlutoCalibStates.CALIB_DONE

    def _calib_done(self, event, mech):
        pass


class PlutoRomAssessStates(Enum):
    FREE_RUNNING = 0
    AROM_ASSESS = 1
    PROM_ASSESS = 1
    ROM_DONE = 2


class PlutoRomAssessmentStateMachine():
    def __init__(self, plutodev):
        self._state = PlutoCalibStates.FREE_RUNNING
        self._pluto = plutodev
        self._stateactions = {
            PlutoRomAssessStates.FREE_RUNNING: self._free_running,
            PlutoRomAssessStates.AROM_ASSESS: self._arom_assess,
            PlutoRomAssessStates.PROM_ASSESS: self._prom_assess,
            PlutoRomAssessStates.ROM_DONE: self._rom_done
        }
    
    @property
    def state(self):
        return self._state

    def run_statemachine(self, event, mech):
        """Execute the state machine depending on the given even that has occured.
        """
        self._stateactions[self._state](event, mech)
    
    def _free_running(self, event, mech):
        # Check if the button release event has happened.
        if event == PlutoButtonEvents.RELEASED:
            # Send the calibration command to the device.
            self._pluto.calibrate(mech)
            return
        # Check of the calibration is done.
        if self._pluto.calibration == pdef.get_code(pdef.CalibrationStatus, "YESCALIB"):
            self._state = PlutoCalibStates.WAIT_FOR_ROM_SET
    
    def _arom_assess(self, event, mech):
        # Check of the calibration is done.
        if self._pluto.calibration == pdef.get_code(pdef.CalibrationStatus, "NOCALIB"):
            self._state = PlutoCalibStates.WAIT_FOR_ZERO_SET
            return
        # Check if the button release event has happened.
        if event == PlutoButtonEvents.RELEASED:
            # Check if the ROM is acceptable.
            _romcheck = (-self._pluto.angle >= 0.9 * pdef.PlutoAngleRanges[mech]
                         and -self._pluto.angle <= 1.1 * pdef.PlutoAngleRanges[mech])
            if _romcheck:
                # Everything looks good. Calibration is complete.
                self._state = PlutoCalibStates.WAIT_FOR_CLOSE
            else:
                # ROM is not acceptable. Calibration Error.
                self._state = PlutoCalibStates.CALIB_ERROR
    
    def _prom_assess(self, event, mech):
        # Check if the button release event has happened.
        if event == PlutoButtonEvents.RELEASED:
            # Calibration all done.
            self._state = PlutoCalibStates.CALIB_DONE
    
    def _rom_done(self, event, mech):
        pass