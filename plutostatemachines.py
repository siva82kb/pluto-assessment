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


class PlutoPropAssessEvents(Enum):
    STARTSTOP_CLICKED = 0
    PAUSE_CLICKED = 1
    HAPTIC_DEMO_TARGET_REACHED_TIMEOUT = 2
    HAPTIC_DEMO_OFF_TARGET_TIMEOUT = 3
    HAPTIC_DEMO_ON_TARGET_TIMEOUT = 4
    FULL_RANGE_REACHED = 5
    INTRA_TRIAL_REST_TIMEOUT = 6
    INTER_TRIAL_REST_TIMEOUT = 7


class PlutoFullAssessEvents(Enum):
    STARTSTOP_CLICKED = 0
    PAUSE_CLICKED = 1
    HAPTIC_DEMO_TARGET_REACHED_TIMEOUT = 2
    HAPTIC_DEMO_OFF_TARGET_TIMEOUT = 3
    HAPTIC_DEMO_ON_TARGET_TIMEOUT = 4
    FULL_RANGE_REACHED = 5
    INTRA_TRIAL_REST_TIMEOUT = 6
    INTER_TRIAL_REST_TIMEOUT = 7

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
    PROM_ASSESS = 2
    ROM_DONE = 3


class PlutoRomAssessmentStateMachine():
    def __init__(self, plutodev, aromval, promval):
        self._state = PlutoRomAssessStates.FREE_RUNNING
        self._instruction = "Select AROM or PROM to assess."
        self._arom = aromval if aromval >= 0 else 0
        self._prom = promval if promval >= 0 else 0
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._apromflag = 0x00
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
    
    @property
    def instruction(self):
        return self._instruction
    
    @property
    def arom(self):
        return self._arom
    
    @property
    def prom(self):
        return self._prom

    def run_statemachine(self, event):
        """Execute the state machine depending on the given even that has occured.
        """
        self._stateactions[self._state](event)
    
    def _free_running(self, event):
        # Wait for AROM or PROM to be selected.
        if event == PlutoRomAssessEvent.AROM_SELECTED:
            self._state = PlutoRomAssessStates.AROM_ASSESS
            self._instruction = "Assessing AROM. Press the PLUTO Button when done."
            self._apromflag |= 0x01
        elif event == PlutoRomAssessEvent.PROM_SELECTED:
            self._state = PlutoRomAssessStates.PROM_ASSESS
            print(self._state)
            self._instruction = "Assessing PROM. Press the PLUTO Button when done."
            self._apromflag |= 0x02
        # Check if both AROM and PROM have been assessed.
        if self._apromflag == 0x03:
            self._instruction = "ROM Assessment Done. Press the PLUTO Button to exit."
            if event == PlutoButtonEvents.RELEASED:
                self._state = PlutoRomAssessStates.ROM_DONE
    
    def _arom_assess(self, event):
        # Check if the button release event has happened.
        if event == PlutoButtonEvents.RELEASED:
            self._arom = abs(self._pluto.hocdisp)
            # Update PROM if needed
            self._prom = self._arom if self._arom > self._prom else self._prom
            # Update the instruction
            self._instruction = "Select AROM or PROM to assess."
            self._state = PlutoRomAssessStates.FREE_RUNNING
 
    def _prom_assess(self, event):
        # Check if the button release event has happened.
        if event == PlutoButtonEvents.RELEASED:
            if abs(self._pluto.hocdisp) >= self._arom:
                self._prom = abs(self._pluto.hocdisp)
                # Update the instruction
                self._instruction = "Select AROM or PROM to assess."
                self._state = PlutoRomAssessStates.FREE_RUNNING
            else:
                # Update the instruction
                self._instruction = "Error! PROM cannot be less than AROM.\nAssessing PROM. Press the PLUTO Button when done."
    
    def _rom_done(self, event):
        pass


class PlutoPropAssessStates(Enum):
    PROP_DONE = 0
    WAIT_FOR_START = 1
    WAIT_FOR_HAPTIC_DISPAY_START = 2
    TRIAL_HAPTIC_DISPLAY_MOVING = 3
    TRIAL_HAPTIC_DISPLAY = 4
    INTRA_TRIAL_REST = 5
    TRIAL_ASSESSMENT = 6
    INTER_TRIAL_REST = 7
    PROTOCOL_PAUSE = 8
    PROTOCOL_STOP = 9


class PlutoPropAssessmentStateMachine():
    def __init__(self, plutodev, protocol, smtimer):
        self._state = PlutoPropAssessStates.WAIT_FOR_START
        self._instruction = "Press the Start Button to start assessment."
        self._protocol = protocol
        self._timer = smtimer
        self._timer.stop()
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._pluto = plutodev
        self._stateactions = {
            PlutoPropAssessStates.WAIT_FOR_START: self._wait_for_start,
            PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START: self._wait_for_haptic_display_start,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING: self._trial_haptic_display_moving,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY: self._trial_haptic_display,
            PlutoPropAssessStates.INTRA_TRIAL_REST: self._intra_trial_rest,
            PlutoPropAssessStates.TRIAL_ASSESSMENT: self._trial_assessment,
            PlutoPropAssessStates.INTER_TRIAL_REST: self._inter_trial_rest,
            PlutoPropAssessStates.PROTOCOL_PAUSE: self._protocol_pause,
            PlutoPropAssessStates.PROTOCOL_STOP: self._protocol_stop,
            PlutoPropAssessStates.PROP_DONE: self._protocol_done
        }
    
    @property
    def state(self):
        return self._state
    
    @property
    def instruction(self):
        return self._instruction
    
    def run_statemachine(self, event, timeval):
        """Execute the state machine depending on the given even that has occured.
        """
        self._stateactions[self._state](event, timeval)
    
    def _wait_for_start(self, event, timeval):
        """Waits till the start button is pressed.
        """
        self._timer.stop()
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            # Check to make sure the angle is close to zero.
            if self._pluto.hocdisp < 0.25:
                self._state = PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
                self._instruction = "Starting the ProprioceptionAssessment Protocol Display."
            else:
                self._instruction = "Hand must be closed before we start."

    def _wait_for_haptic_display_start(self, event, timeval):
        self._timer.stop()
        if event == PlutoButtonEvents.RELEASED:
            self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING
            self._instruction = "Running Haptic Display"

    def _trial_haptic_display_moving(self, event, timeval):
        # Check if the target has been reached.
        if event == PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT:
            self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY
            # Wait for the demo duration at the target.
            self._timer.start(1000)


    def _trial_haptic_display(self, event, timeval):
        # Check if the target has been reached.
        if event == PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT:
            self._state = PlutoPropAssessStates.INTRA_TRIAL_REST

    def _intra_trial_rest(self, event, timeval):
        pass

    def _trial_assessment(self, event, timeval):
        pass

    def _inter_trial_rest(self, event, timeval):
        pass

    def _protocol_pause(self, event, timeval):
        pass

    def _protocol_stop(self, event, timeval):
        pass

    def _protocol_done(self, event, timeval):
        pass


class PlutoFullAssessStates(Enum):
    WAIT_FOR_SUBJECT_SELECT = 0
    WAIT_FOR_LIMB_SELECT = 0
    WAIT_FOR_MECHANISM_SELECT = 1
    WAIT_FOR_CALIBRATE = 2
    WAIT_FOR_DISCREACH_ASSESS = 3
    WAIT_FOR_PROP_ASSESS = 4
    WAIT_FOR_FCTRL_ASSESS = 5
    TASK_DONE = 6
    MECHANISM_DONE = 7
    SUBJECT_LIMB_DONE = 8


class PlutoFullAssessmentStateMachine():
    def __init__(self, plutodev, protocol, smtimer, progconsole):
        self._state = PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT
        self._instruction = ""
        self._protocol = protocol
        self._timer = smtimer
        self._timer.stop()
        self._pconsole = progconsole
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._pluto = plutodev
        self._stateactions = {
            PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT: self._wait_for_subject_select,
            PlutoFullAssessStates.WAIT_FOR_LIMB_SELECT: self._wait_for_limb_select,
            PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT: self._wait_for_mechanism_select,
            PlutoFullAssessStates.WAIT_FOR_CALIBRATE: self._wait_for_calibrate,
            PlutoFullAssessStates.WAIT_FOR_DISCREACH_ASSESS: self._wait_for_discreach_assess,
            PlutoFullAssessStates.WAIT_FOR_PROP_ASSESS: self._wait_for_prop_assess,
            PlutoFullAssessStates.WAIT_FOR_FCTRL_ASSESS: self._wait_for_fctrl_assess,
            PlutoFullAssessStates.TASK_DONE: self._task_done,
            PlutoFullAssessStates.MECHANISM_DONE: self._wait_for_mechanism_done,
            PlutoFullAssessStates.SUBJECT_LIMB_DONE: self._wait_for_subject_limb_done,
        }
    
    @property
    def state(self):
        return self._state
    
    @property
    def instruction(self):
        return self._instruction
    
    def run_statemachine(self, event, timeval):
        """Execute the state machine depending on the given even that has occured.
        """
        self._stateactions[self._state](event, timeval)

    def _wait_for_subject_select(self, event, timeval):
        """
        """
        pass
    
    def _wait_for_limb_select(self, event, timeval):
        """
        """
        pass

    def _wait_for_mechanism_select(self, event, timeval):
        """
        """
        pass

    def _wait_for_calibrate(self, event, timeval):
        """
        """
        pass

    def _wait_for_discreach_assess(self, event, timeval):
        """
        """
        pass

    def _wait_for_prop_assess(self, event, timeval):
        """
        """
        pass

    def _wait_for_fctrl_assess(self, event, timeval):
        """
        """
        pass

    def _task_done(self, event, timeval):
        """
        """
        pass

    def _wait_for_mechanism_done(self, event, timeval):
        """
        """
        pass

    def _wait_for_subject_limb_done(self, event, timeval):
        """
        """
        pass

    
    # def _wait_for_start(self, event, timeval):
    #     """Waits till the start button is pressed.
    #     """
    #     self._timer.stop()
    #     if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
    #         # Check to make sure the angle is close to zero.
    #         if self._pluto.hocdisp < 0.25:
    #             self._state = PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
    #             self._instruction = "Starting the ProprioceptionAssessment Protocol Display."
    #         else:
    #             self._instruction = "Hand must be closed before we start."

    # def _wait_for_haptic_display_start(self, event, timeval):
    #     self._timer.stop()
    #     if event == PlutoButtonEvents.RELEASED:
    #         self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING
    #         self._instruction = "Running Haptic Display"

    # def _trial_haptic_display_moving(self, event, timeval):
    #     # Check if the target has been reached.
    #     if event == PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT:
    #         self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY
    #         # Wait for the demo duration at the target.
    #         self._timer.start(1000)


    # def _trial_haptic_display(self, event, timeval):
    #     # Check if the target has been reached.
    #     if event == PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT:
    #         self._state = PlutoPropAssessStates.INTRA_TRIAL_REST

    # def _intra_trial_rest(self, event, timeval):
    #     pass

    # def _trial_assessment(self, event, timeval):
    #     pass

    # def _inter_trial_rest(self, event, timeval):
    #     pass

    # def _protocol_pause(self, event, timeval):
    #     pass

    # def _protocol_stop(self, event, timeval):
    #     pass

    # def _protocol_done(self, event, timeval):
    #     pass
