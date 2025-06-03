"""
Module for handling the operation of the PLUTO proprioceptive assesmsent
window.

Author: Sivakumar Balasubramanian
Date: 22 August 2024
Email: siva82kb@gmail.com
"""


import sys
import inspect
import numpy as np

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,
    QtGui)
from PyQt5.QtCore import (
    pyqtSignal,
    QTimer
)
import pyqtgraph as pg

from enum import Enum, auto
from datetime import datetime as dt

import json
import random
import winsound

import plutodefs as pdef
from ui_plutopropassessctrl import Ui_ProprioceptionAssessWindow
from ui_plutoapromassess import Ui_APRomAssessWindow
from plutodataviewwindow import PlutoDataViewWindow
import plutoassessdef as passdef
import plutofullassessdef as pfadef
import plutoapromwindow as apromwnd
import misc 

from plutofullassessdef import ProprioceptionConstants as PropConst


# Module level constants
BEEP_FREQ = 2500  # Set Frequency To 2500 Hertz
BEEP_DUR = 1000  # Set Duration To 1000 ms == 1 second


# Some useful lambda functions
del_time = lambda x: dt.now() - (dt.now() if x is None else x) 
increment_time = lambda x : x + passdef.PROPASS_CTRL_TIMER_DELTA if x  >= 0 else -1
clip = lambda x: min(max(0, x), 1)
mjt = lambda x: np.polyval([6, -15, 10, 0, 0, 0], clip(x))


class PlutoPropAssessEvents(Enum):
    STARTSTOP_CLICKED = 0
    PAUSE_CLICKED = auto()
    HAPTIC_DEMO_TARGET_REACHED_TIMEOUT = auto()
    HAPTIC_DEMO_OFF_TARGET_TIMEOUT = auto()
    HAPTIC_DEMO_ON_TARGET_TIMEOUT = auto()
    FULL_RANGE_REACHED = auto()
    INTRA_TRIAL_REST_TIMEOUT = auto()
    INTER_TRIAL_REST_TIMEOUT = auto()
    TRIAL_NO_RESPONSE_TIMOUT = auto()
    TRIAL_RESPONSE_HOLD_TIMEOUT = auto()
    ALL_TARGETS_DONE = auto()


class PlutoPropAssessAction(Enum):
    SET_CONTROl_TO_NONE = 0
    SET_CONTROL_TO_POSITION = auto()
    SET_HAPTIC_DEMO_TARGET_POSITION = auto()
    SET_HOME_POSITION = auto()
    SET_ASSESSMENT_TARGET_POSITION = auto()
    DO_NOTHING = auto()


class PlutoPropAssessStates(Enum):
    PROP_DONE = 0
    FREE_RUNNING = auto()
    WAIT_FOR_HAPTIC_DISPAY_START = auto()
    TRIAL_HAPTIC_DISPLAY_MOVING = auto()
    TRIAL_HAPTIC_DISPLAY = auto()
    INTRA_TRIAL_REST = auto()
    TRIAL_ASSESSMENT_MOVING = auto()
    TRIAL_ASSESSMENT_RESPONSE_HOLD = auto()
    TRIAL_ASSESSMENT_NO_RESPONSE_HOLD = auto()
    INTER_TRIAL_REST = auto()
    PROTOCOL_PAUSE = auto()
    PROTOCOL_STOP = auto()


class PlutoPropAssessData():
    def __init__(self, assessinfo: dict):
        self._assessinfo = assessinfo
        self._demomode = None
        # Trial variables
        self._currtrial = 0
        self._startpos = None
        self._trialpos = []
        self._trialdata = {"dt": [], "pos": [], "vel": []}
        self._currtrial = -1
        self._targets = []
        
        # Propprioceptive assessment position
        self._proppostorq = [[] for _ in range(self.ntrials)]
        
        # Generate targets.
        self._generate_targets()

        # Logging variables
        self._logstate: apromwnd.APROMRawDataLoggingState = apromwnd.APROMRawDataLoggingState.WAIT_FOR_LOG
        self._rawfilewriter: misc.CSVBufferWriter = misc.CSVBufferWriter(
            self.rawfile, 
            header=pfadef.RAWDATA_HEADER
        )
        self._summaryfilewriter: misc.CSVBufferWriter = misc.CSVBufferWriter(
            self.summaryfile, 
            header=PropConst.SUMMARY_HEADER,
            flush_interval=0.0,
            max_rows=1
        )

    @property
    def type(self):
        return self._assessinfo["type"]
    
    @property
    def limb(self):
        return self._assessinfo["limb"]
    
    @property
    def mechanism(self):
        return self._assessinfo['mechanism']
    
    @property
    def session(self):
        return self._assessinfo['session']

    @property
    def ntrials(self):
        return pfadef.ProprioceptionConstants.NO_OF_TRIALS
    
    @property
    def rawfile(self):
        return self._assessinfo['rawfile']
    
    @property
    def summaryfile(self):
        return self._assessinfo['summaryfile']
    
    @property
    def arom(self):
        return self._assessinfo["arom"]

    @property
    def prom(self):
        return self._assessinfo["prom"]

    @property
    def currtrial(self):
        return self._currtrial
    
    @property
    def targets(self):
        return self._targets
    
    @property
    def prop_pos_torq(self):
        return self._proppostorq
    
    @property
    def startpos(self):
        return self._startpos
    
    @property
    def trialdata(self):
        return self._trialdata
    
    @property
    def demomode(self):
        return self._demomode
    
    @demomode.setter
    def demomode(self, value):
        self._demomode = value

    @property
    def logstate(self):
        return self._logstate
        
    @property
    def all_trials_done(self):
        """Check if all trials are done.
        """
        return self._currtrial >= self.ntrials
    
    @property
    def rawfilewriter(self):
        return self._rawfilewriter
    
    def get_current_target(self, demomode=False):
        """Get the current target position for the trial.
        """
        # Check if in demomode.
        if demomode:
            return (0.75 * np.random.rand() + 0.25) * self.prom[1]
        # Not in demo mode. 
        if self._currtrial < 0 or self._currtrial >= self.ntrials:
            return None
        return self._targets[self._currtrial]
    
    def start_newtrial(self, reset: bool = False):
        """Start a new trial.
        """
        if self._currtrial < self.ntrials:
            self._startpos = None
            self._trialpos = []
            self._trialdata = {"dt": [], "pos": [], "vel": []}
            self._currtrial = 0 if reset else self._currtrial + 1

    def add_newdata(self, dt, pos):
        """Add new data to the trial data.
        """
        self._trialdata['dt'].append(dt)
        self._trialdata['pos'].append(pos)
        self._trialdata['vel'].append((pos - self._trialdata['pos'][-2]) / dt
                                      if len(self._trialdata['pos']) > 1
                                      else 0)
        if len(self._trialdata['dt']) > pfadef.POS_VEL_WINDOW_LENGHT:
            self._trialdata['dt'].pop(0)
            self._trialdata['pos'].pop(0)
            self._trialdata['vel'].pop(0)
    
    def set_prop_assessment(self):
        """Set the proprioceptive assessment value for the given trial.
        """
        # Update ROM 
        self._rom[self._currtrial] = [self._trialrom[0], self._trialrom[-1]]
        # Update the summary file.
        self._summaryfilewriter.write_row([
            self.session,
            self.type,
            self.limb,
            self.mechanism,
            self.currtrial,
            self._startpos,
            self._trialrom[0],
            self._trialrom[-1],
            self._trialrom[-1] - self._trialrom[0],
            0,
            0
        ])
        
    def set_startpos(self):
        """Sets the start position as the average of trial data.
        """
        self._startpos = float(np.mean(self._trialdata['pos']))
        self._trialrom = [self._startpos]

    def start_rawlogging(self):
        self._logstate = apromwnd.APROMRawDataLoggingState.LOG_DATA
    
    def terminate_rawlogging(self):
        self._logstate = apromwnd.APROMRawDataLoggingState.LOGGING_DONE
        self._rawfilewriter.close()
        self._rawfilewriter = None
    
    def terminate_summarylogging(self):
        self._summaryfilewriter.close()
        self._summaryfilewriter = None
    
    def _generate_targets(self):
        _tgtsep = PropConst.TGT_POSITIONS[0] * self.prom[1]
        _tgts = (PropConst.TGT_POSITIONS
                 if _tgtsep >= PropConst.MIN_TGT_SEP
                 else PropConst.TGT_POSITIONS[1:2])
        # Generate the randomly order targets
        _tgts = PropConst.NO_OF_TRIALS * _tgts
        random.shuffle(_tgts)
        self._targets = (self.prom[1] * np.array(_tgts)).tolist()
    
    def _get_trial_details_line(self, demomode=False, state="Haptic Demo"):
        # In demo mode.
        if demomode:
            pass
        # Not in demo mode.
        _dispstr = [
            "Trial: " + 
            f"{self.currtrial:3d} / {self.ntrials:3d}"
            if self.currtrial > 0
            else f"- NA -"
        ]
        _dispstr += [
            "Target: " +
            f"{self.get_current_target():5.1f}cm"
            if self.get_current_target() is not None
            else "- NA -"
        ] 
        return _dispstr


class PlutoPropAssessmentStateMachine():
    def __init__(self, plutodev: QtPluto, data: PlutoPropAssessData, instdisp):
        self._state = PlutoPropAssessStates.FREE_RUNNING
        self._instruction = "Press the Start Button to start assessment."
        self._statetimer = 0
        self._data = data
        self._instruction = f""
        self._instdisp = instdisp
        self._pluto = plutodev
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._stateactions = {
            PlutoPropAssessStates.FREE_RUNNING: self._free_running,
            PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START: self._wait_for_haptic_display_start,
            # PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING: self._trial_haptic_display_moving,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY: self._trial_haptic_display,
            PlutoPropAssessStates.INTRA_TRIAL_REST: self._intra_trial_rest,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING: self._trial_assessment_moving,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD: self._trial_assessment_response_hold,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD: self._trial_assessment_no_response_hold,
            PlutoPropAssessStates.INTER_TRIAL_REST: self._inter_trial_rest,
            PlutoPropAssessStates.PROTOCOL_PAUSE: self._protocol_pause,
            PlutoPropAssessStates.PROTOCOL_STOP: self._protocol_stop,
            PlutoPropAssessStates.PROP_DONE: self._protocol_done
        }
        # Start a new trial.
        self._data.start_newtrial()
    
    @property
    def state(self):
        return self._state
    
    @property
    def instruction(self):
        return self._instruction
    
    @property
    def addn_info(self):
        return self._addn_info
    
    def run_statemachine(self, event, dt) -> PlutoPropAssessAction:
        """Execute the state machine depending on the given even that has occured.
        """
        self._addn_info = None
        return self._stateactions[self._state](event, dt)
    
    def _free_running(self, event, dt) -> PlutoPropAssessAction:
        """Waits till the start button is pressed.
        """
        # Check if all trials are done or if we are in the demo mode.

        if event == pdef.PlutoEvents.RELEASED:
            # Check to make sure the angle is close to zero.
            if self._pluto.hocdisp < PropConst.START_POSITION_TH:
                self._state = PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
                self._statetimer = 0.5
                self._instruction = "Starting the ProprioceptionAssessment Protocol Display."
                return PlutoPropAssessAction.SET_CONTROL_TO_POSITION
            else:
                self._instruction = "Hand must be closed before we start."
        return PlutoPropAssessAction.SET_CONTROl_TO_NONE

    def _wait_for_haptic_display_start(self, event, dt) -> PlutoPropAssessAction:
        if event == pdef.PlutoEvents.NEWDATA:
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY
                self._instruction = "Starting Haptic Demo. Relax."
                return PlutoPropAssessAction.SET_HAPTIC_DEMO_TARGET_POSITION
        return PlutoPropAssessAction.SET_CONTROL_TO_POSITION

    # def _trial_haptic_display_moving(self, event, dt) -> PlutoPropAssessAction:
    #     if event == pdef.PlutoEvents.NEWDATA:
    #         self._statetimer -= dt
    #         if self._statetimer <= 0:
    #             self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY
    #             self._instruction = "Waiting for hand to be closed."
    #             return PlutoPropAssessAction.SET_HAPTIC_DEMO_HOME_POSITION


        # # Target not reached
        # if abs(_tgterr) > self._protocol['target_error_th']:
        #     self._time = 0
        #     return False
        
        # # Target reached
        # # Check if the target has been maintained for the required duration.
        # if self._time >= self._protocol['on_off_target_dur']:
        #     # Target maintained. Move to next state.
        #     return self._smachine.run_statemachine(
        #         PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT,
        #         0
        #     )
        # return False
        # Check if the target has been reached.
        # if event == PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT:
        #     self._state = PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY
        #     return True
        # if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
        #     self._state = PlutoPropAssessStates.PROTOCOL_STOP
        #     return True
        # return False

    def _trial_haptic_display(self, event, dt) -> PlutoPropAssessAction:
        # Check if the target has been reached.
        if event == PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT:
            self._state = PlutoPropAssessStates.INTRA_TRIAL_REST
            return PlutoPropAssessAction.DO_NOTHING
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return PlutoPropAssessAction.DO_NOTHING
        return PlutoPropAssessAction.DO_NOTHING

    def _intra_trial_rest(self, event, dt) -> PlutoPropAssessAction:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.INTER_TRIAL_REST_TIMEOUT:
            self._state = PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _trial_assessment_moving(self, event, dt) -> PlutoPropAssessAction:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.TRIAL_NO_RESPONSE_TIMOUT:
            self._addn_info = False
            self._state = PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD
            return True
        if event == pdef.PlutoEvents.RELEASED:
            self._addn_info = True
            self._state = PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _trial_assessment_response_hold(self, event, dt) -> PlutoPropAssessAction:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.TRIAL_RESPONSE_HOLD_TIMEOUT:
            self._addn_info = False
            self._state = PlutoPropAssessStates.INTER_TRIAL_REST
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _trial_assessment_no_response_hold(self, event, dt) -> PlutoPropAssessAction:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.TRIAL_RESPONSE_HOLD_TIMEOUT:
            self._addn_info = False
            self._state = PlutoPropAssessStates.INTER_TRIAL_REST
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _inter_trial_rest(self, event, dt) -> PlutoPropAssessAction:
        # Check if the intra-trial rest duration is complete
        if event == PlutoPropAssessEvents.INTER_TRIAL_REST_TIMEOUT:
            self._addn_info = False
            self._state = PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
            return True
        if event == PlutoPropAssessEvents.ALL_TARGETS_DONE:
            self._addn_info = False
            self._state = PlutoPropAssessStates.PROP_DONE
            return True
        if event == PlutoPropAssessEvents.STARTSTOP_CLICKED:
            self._state = PlutoPropAssessStates.PROTOCOL_STOP
            return True
        return False

    def _protocol_pause(self, event, dt) -> PlutoPropAssessAction:
        return False

    def _protocol_stop(self, event, dt) -> PlutoPropAssessAction:
        if event == PlutoPropAssessEvents.ALL_TARGETS_DONE:
            self._addn_info = False
            self._state = PlutoPropAssessStates.PROP_DONE
            return True
        return False

    def _protocol_done(self, event, dt) -> PlutoPropAssessAction:
        return False
    
    #
    # Supporting functions
    #
    def subj_is_holding(self):
        """Check if the subject is holding the position.
        """
        _th = (pfadef.VEL_HOC_THRESHOLD
               if self._data.mechanism == "HOC"
               else pfadef.VEL_NOT_HOC_THRESHOLD)
        return bool(np.all(np.abs(self._data.trialdata['vel']) < _th))
    
    def subj_in_target(self) -> bool:
        """Check if the subejct is close to the target position.
        """
        return np.abs(self._data.get_current_target() - self._pluto.hocdisp) < PropConst.TARGET_ERROR_TH


class PlutoPropAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO proprioceptive assessment window.
    """

    def __init__(self, parent=None, plutodev: QtPluto=None, assessinfo: dict=None,
                 modal=False, dataviewer=False, onclosecb=None, heartbeat=False):
        """
        Constructor for the PlutoPropAssessWindow class.
        """
        super(PlutoPropAssessWindow, self).__init__(parent)
        self.ui = Ui_APRomAssessWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # Set the title of the window.
        self.setWindowTitle(
            " | ".join((
                "PLUTO Full Assessment",
                "Hand Proprioception",
                f"{assessinfo['subjid'] if 'subjid' in assessinfo else ''}",
                f"{assessinfo['type'] if 'type' in assessinfo else ''}",
                f"{assessinfo['limb'] if 'limb' in assessinfo else ''}",
                f"{assessinfo['mechanism'] if 'mechanism' in assessinfo else ''}",
                f"{assessinfo['session'] if 'session' in assessinfo else ''}",
            ))
        )

        # PLUTO device
        self._pluto = plutodev

        # Heartbeat timer
        self._heartbeat = heartbeat
        if self._heartbeat:
            self.heartbeattimer = QTimer()
            self.heartbeattimer.timeout.connect(lambda: self.pluto.send_heartbeat())
            self.heartbeattimer.start(250)
        
        # Prioprioceptive assessment data
        self.data: PlutoPropAssessData = PlutoPropAssessData(assessinfo=assessinfo)

        # Set control to NONE
        self.pluto.send_heartbeat()
        self._pluto.set_control_type("TORQUE")

        # Initialize graph for plotting
        self._propassess_add_graph()

        # Initialize the state machine.
        self._smachine = PlutoPropAssessmentStateMachine(
            plutodev=self._pluto,
            data=self.data,
            instdisp=self.ui.subjInst
        )
        
        # Attach callbacks
        self._attach_pluto_callbacks()

        # Attach control callbacks
        self.ui.cbTrialRun.clicked.connect(self._callback_trialrun_clicked)

        # Attach callbacks
        self.pluto.newdata.connect(self._callback_pluto_newdata)
        self.pluto.btnreleased.connect(self._callback_pluto_btn_released)

        # Define handlers for different states.
        self._state_handlers = {
            PlutoPropAssessStates.FREE_RUNNING: self._handle_wait_for_start,
            # PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START: self._handle_wait_for_haptic_display_start,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING: self._handle_trial_haptic_display_moving,
            PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY: self._handle_trial_haptic_display,
            PlutoPropAssessStates.INTRA_TRIAL_REST: self._handle_intra_trial_rest,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING: self._handle_trial_assessment_moving,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD: self._handle_trial_assessment_response_hold,
            PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD: self._handle_trial_assessment_no_response_hold,
            PlutoPropAssessStates.INTER_TRIAL_REST: self._handle_inter_trial_rest,
            PlutoPropAssessStates.PROTOCOL_PAUSE: self._handle_protocol_pause,
            PlutoPropAssessStates.PROTOCOL_STOP: self._handle_protocol_stop,
            PlutoPropAssessStates.PROP_DONE: self._handle_protocol_done
        }
        
        # Update UI.
        self.update_ui()

        # Initialize PLUTO control to NONE.
        self.pluto.set_control_type("NONE")

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
    
    @property
    def arom(self):
        return self._arom
    
    @property
    def prom(self):
        return self._prom
    
    @property
    def outdir(self):
        return self._outdir
    
    #
    # Control Callbacks
    #    
    def _callback_trialrun_clicked(self):
        if self.data.demomode is None and self.ui.cbTrialRun.isChecked():
            self.data.demomode = True
        if self.data.demomode and not self.ui.cbTrialRun.isChecked():
            self.data.demomode = False
            # Restart ROM assessment statemachine
            self._smachine.reset_statemachine()

    #
    # Window close event
    # 
    def closeEvent(self, event):
        if self.on_close_callback:
            self.on_close_callback(data=self.data.rom)
        # Set device to no control.
        self.pluto.set_control_type("NONE")
        # Detach PLUTO callbacks.
        self._detach_pluto_callbacks()
        # # Close file if open
        # if self._data['trialfhandle'] is not None:
        #     self._data['trialfhandle'].flush()
        #     self._data['trialfhandle'].close()
        return super().closeEvent(event)

    #
    # Update UI
    #
    def update_ui(self):
        # Demo run checkbox
        if self.ui.cbTrialRun.isEnabled():
            _cond1 = self.data.demomode is False
            _cond2 = (self.data.demomode is None
                      and self._smachine.state == PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START)
            if _cond1 or _cond2:
                self.ui.cbTrialRun.setEnabled(False)

        # Update current hand position
        if self.pluto.hocdisp is None:
            return
        
        # Update the graph display
        self._update_graph()

        # Update based on state
        _dispstr = [f"Hand Aperture: {self._pluto.hocdisp:5.2f}cm"]
        if self._smachine.state == PlutoPropAssessStates.FREE_RUNNING:
            pass
        elif self._smachine.state == PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START:
            _dispstr += self.data._get_trial_details_line(demomode=False, state="Haptic Demo")
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            _dispstr += self.data._get_trial_details_line(demomode=False, state="Haptic Demo")
            # self.ui.checkBoxPauseProtocol.setEnabled(False)
        # elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
        #     _trlines = self._get_trial_details_line("Haptic Demo")
        #     _dispstr += _trlines + ["Moving to target position.", 
        #                             "", str(self._smachine.state)]
        # elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
        #     _trlines = self._get_trial_details_line("Haptic Demo")
        #     _dispstr += _trlines + ["Demonstraing Haptic Position.",
        #                             "", str(self._smachine.state)]
        # elif self._smachine.state == PlutoPropAssessStates.INTRA_TRIAL_REST:
        #     _trlines = self._get_trial_details_line("Waiting for hand to be closed.")
        #     _dispstr += _trlines + ["", str(self._smachine.state)]
        # elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING:
        #     _trlines = self._get_trial_details_line("Assessing proprioception.")
        #     _dispstr += _trlines + ["", str(self._smachine.state)]
        # elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD:
        #     _trlines = self._get_trial_details_line("Holding Sensed Position.")
        #     _dispstr += _trlines + ["", str(self._smachine.state)]
        # elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD:
        #     _trlines = self._get_trial_details_line("Holding Max. Position (No Response).")
        #     _dispstr += _trlines + ["", str(self._smachine.state)]
        # elif self._smachine.state == PlutoPropAssessStates.INTER_TRIAL_REST:
        #     _trlines = self._get_trial_details_line("Waiting for the hand to be closed.")
        #     _dispstr += _trlines + ["", str(self._smachine.state)]
        # elif self._smachine.state == PlutoPropAssessStates.PROP_DONE:
        #      _trlines = self._get_trial_details_line(f"All {len(self._data['targets'])} trials completed! You can close the window.")
        #      _dispstr += ["", _trlines[1]] + ["", str(self._smachine.state)]
        #     #  self.ui.pbStartStopProtocol.setEnabled(False)
        # elif self._smachine.state == PlutoPropAssessStates.PROTOCOL_STOP:
        #      _trlines = self._get_trial_details_line(f"Stopping protocol.")
        #      _dispstr += _trlines + ["", str(self._smachine.state)]
            #  self.ui.pbStartStopProtocol.setEnabled(False)

        # Update text.
        self.ui.lblTitle.setText(" | ".join(_dispstr))
        # self.ui.textInformation.setText("\n".join(_dispstr))

        # Update status message
        self.ui.lblStatus.setText(f"{self.pluto.error} | {self.pluto.controltype} | {self._smachine.state}")

    def _update_graph(self):
        # Current position.
        self.ui.currPosLine1.setData(
            [self.pluto.hocdisp, self.pluto.hocdisp],
            [-40, 20]
        )
        self.ui.currPosLine2.setData(
            [-self.pluto.hocdisp, -self.pluto.hocdisp],
            [-40, 20]
        )
        # Update target position when needed.
        _checkstate = not (
            self._smachine.state == PlutoPropAssessStates.FREE_RUNNING
            or self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING
            or self._smachine.state == PlutoPropAssessStates.INTER_TRIAL_REST
            or self._smachine.state == PlutoPropAssessStates.PROTOCOL_STOP
            or self._smachine.state == PlutoPropAssessStates.PROP_DONE
        )
        _tgt = self.data.get_current_target(False) if _checkstate else 0
        # Update target line        
        self.ui.tgtLine1.setData(
            [_tgt, _tgt],
            [-40, 20]
        )
        self.ui.tgtLine2.setData(
            [-_tgt, -_tgt],
            [-40, 20]
        )

    #
    # Graph plot initialization
    #
    def _propassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self.ui.hocGraph.setLayout(_templayout)
        _pgobj.setYRange(-30, 30)
        if self.data.mechanism == "HOC":
            _pgobj.setXRange(-10, 10)
        else:
            _pgobj.setXRange(pdef.PlutoAngleRanges[self.data.mechanism][0],
                             pdef.PlutoAngleRanges[self.data.mechanism][1])
        # _pgobj.setXRange(-10, 10)
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Current position lines
        self.ui.currPosLine1 = pg.PlotDataItem(
            [0, 0],
            [-40, 20],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        self.ui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [-40, 20],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        _pgobj.addItem(self.ui.currPosLine1)
        _pgobj.addItem(self.ui.currPosLine2)
        
        # AROM Lines
        self.ui.aromLine1 = pg.PlotDataItem(
            [self.data.arom[1], self.data.arom[1]],
            [-40, 20],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        self.ui.aromLine2 = pg.PlotDataItem(
            [-self.data.arom[1], -self.data.arom[1]],
            [-40, 20],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self.ui.aromLine1)
        _pgobj.addItem(self.ui.aromLine2)
        
        # PROM Lines
        self.ui.promLine1 = pg.PlotDataItem(
            [self.data.prom[1], self.data.prom[1]],
            [-40, 20],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        self.ui.promLine2 = pg.PlotDataItem(
            [-self.data.prom[1], -self.data.prom[1]],
            [-40, 20],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self.ui.promLine1)
        _pgobj.addItem(self.ui.promLine2)
        
        # Target Lines
        self.ui.tgtLine1 = pg.PlotDataItem(
            [0, 0],
            [-40, 20],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        self.ui.tgtLine2 = pg.PlotDataItem(
            [0, 0],
            [-40, 20],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        _pgobj.addItem(self.ui.tgtLine1)
        _pgobj.addItem(self.ui.tgtLine2)

        # Instruction text
        self.ui.subjInst = pg.TextItem(text='', color='w', anchor=(0.5, 0.5))
        self.ui.subjInst.setPos(0, 30)  # Set position (x, y)
        # Set font and size
        self.ui.subjInst.setFont(QtGui.QFont("Bahnschrift Light", 16))
        _pgobj.addItem(self.ui.subjInst)

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
        _action = self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA,
            self.pluto.delt()
        )
        self._perform_action(_action)
        # # Write data row to the file.
        # if self._data['trialfhandle'] is not None:
        #     try:
        #         # time,status,error,mechanism,angle,hocdisp,torque,control,target,button,framerate,state
        #         self._data['trialfhandle'].write(",".join((
        #             dt.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        #             f"{self._pluto.status}",
        #             f"{self._pluto.error}",
        #             f"{self._pluto.mechanism}",
        #             f"{self._pluto.angle:0.3f}",
        #             f"{self._pluto.hocdisp:0.3f}",
        #             f"{self._pluto.torque:0.3f}",
        #             f"{self._pluto.control:0.3f}",
        #             f"{self._pluto.target:0.3f}",
        #             f"{self._pluto.button}",
        #             f"{self._pluto.framerate():0.3f}",
        #             f"{self._smachine.state}".split('.')[-1]
        #         )))
        #         self._data['trialfhandle'].write("\n")
        #     except ValueError:
        #         self._data['trialfhandle'] = None
        # self._state_handlers[self._smachine.state](_strans)
        if np.random.rand() < 0.1:
            self.update_ui()

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        _action = self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED,
            self.pluto.delt()
        )
        self._perform_action(_action)
        # self._state_handlers[self._smachine.state](_strans)
        self.update_ui()

    #
    # Control Callbacks
    #
    def _callback_propprotocol_startstop(self, event):
        # Check if this is a start or stop event.
        if self._smachine.state == PlutoPropAssessStates.WAIT_FOR_START:
            # Start start time
            self._data["assess_strt_t"] = dt.now()
            self._data["trial_strt_t"] = dt.now()
            
            # Check if there is a valid next target
            if self._are_all_trials_done(): 
                # All done.
                return self._smachine.run_statemachine(
                    PlutoPropAssessEvents.ALL_TARGETS_DONE,
                    0
                )
            else:
                # Start event
                _strans = self._smachine.run_statemachine(
                    PlutoPropAssessEvents.STARTSTOP_CLICKED,
                    self._time
                )
        else:
            # self.ui.pbStartStopProtocol.setEnabled(False)
            # Stop event
            _strans = self._smachine.run_statemachine(
                PlutoPropAssessEvents.STARTSTOP_CLICKED,
                self._time
            )
        # Handle the current proprioceptuive assessment state
        self._state_handlers[self._smachine.state](_strans)

        self.update_ui()
    
    def _callback_ctrl_timer(self):
        # Check state and act accordingly.
        self._tgtctrl['time'] = increment_time(self._tgtctrl['time'])
        self._time = increment_time(self._time)
        _strans = False
        if self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            # Update target position.
            self._update_target_position()

            # Check if the target has been reached, and target demo time has lapsed.
            _strans = self._check_target_display_timeout()
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            # Check if the statemachine timer has reached the required duration.
            if self._time >= self._protocol['demo_dur']:
                # Demo duration reached. Move to next state.
                _strans = self._smachine.run_statemachine(
                    PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT,    
                    0
                )
        elif self._smachine.state == PlutoPropAssessStates.INTRA_TRIAL_REST:
            # Update target position.
            self._update_target_position_mjt()
            # Check if hand has been clopsed, and target intra-trial duration 
            # has lapsed.
            _strans = self._check_intratrial_timeout()
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING:
            # Update target position.
            self._update_target_position()
            # Check if PROM is reached, and if time has run out.
            _strans = self._check_trial_no_respose_timeout()
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_RESPONSE_HOLD:
            # Check if the statemachine timer has reached the required duration.
            _strans = self._check_trial_hold_timeout()
        elif self._smachine.state == PlutoPropAssessStates.TRIAL_ASSESSMENT_NO_RESPONSE_HOLD:
            # Check if the statemachine timer has reached the required duration.
            _strans = self._check_trial_hold_timeout()
        elif self._smachine.state == PlutoPropAssessStates.INTER_TRIAL_REST:
            # Update target position.
            self._update_target_position_mjt()
            # Check if the target has been reached, and target demo time has lapsed.
            _strans = self._check_inter_trial_timeout()
        elif self._smachine.state == PlutoPropAssessStates.PROTOCOL_STOP:
            # Update target position.
            self._update_target_position_mjt()
            # Check if the target has been reached, and target demo time has lapsed.
            _strans = self._check_protocol_stop_timeout()

        # Handle the current proprioceptuive assessment state
        self._state_handlers[self._smachine.state](_strans)

        # Update UI
        self.update_ui()

    # def _check_target_display_timeout(self) -> bool:
    #     _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
        
    #     # Target not reached
    #     if abs(_tgterr) > self._protocol['target_error_th']:
    #         self._time = 0
    #         return False
        
    #     # Target reached
    #     # Check if the target has been maintained for the required duration.
    #     if self._time >= self._protocol['on_off_target_dur']:
    #         # Target maintained. Move to next state.
    #         return self._smachine.run_statemachine(
    #             PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT,
    #             0
    #         )
    #     return False

    def _check_intratrial_timeout(self) -> bool:
        # Hand not closed.
        if self.pluto.hocdisp >= 0.25:
            self._time = 0
            return False
        
        # Hand closed
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['intrat_rest_dur']:
            # Target maintained. Move to next state.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.INTER_TRIAL_REST_TIMEOUT,
                0
            )
        return False

    def _check_trial_no_respose_timeout(self) -> bool:
        _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
        # Target not reached
        if abs(_tgterr) >= self._protocol['target_error_th']:
            self._time = 0
            return False
        
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['trial_no_response_dur']:
                # Target maintained. Move to next state.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.TRIAL_NO_RESPONSE_TIMOUT,
                0
            )
        return False
    
    def _check_trial_hold_timeout(self) -> bool:
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['trial_assess_hold_dur']:
            # Demo duration reached. Move to next state.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.TRIAL_RESPONSE_HOLD_TIMEOUT,    
                0
            )
        return False
    
    def _check_inter_trial_timeout(self) -> bool:
        _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
        
        # Target not reached
        if abs(_tgterr) > self._protocol['target_error_th']:
            self._time = 0
            return False
        
        # Target reached
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['intert_rest_dur']:
            # Close trial data file.
            self._data['trialfhandle'].flush()
            self._data['trialfhandle'].close()
            self._data['trialfile'] = ""
            self._data['trialfhandle'] = None

            # Write summary details.
            with open(self._summary['file'], "a") as fh:
                fh.write(",".join((
                    f"{self._data['trialno']+1}",
                    f"{self._data['targets'][self._data['trialno']]}",
                    f"{np.mean(self._summary['shownpos']):0.3f}",
                    f"{np.mean(self._summary['sensedpos']) if len(self._summary['sensedpos']) > 0 else -1:0.3f}",
                )))
                fh.write("\n")
            # Reset summary position data
            self._summary['shownpos'] = []
            self._summary['sensedpos'] = []

            # Check if there is a valid next target
            if self._are_all_trials_done(): 
                # All done.
                return self._smachine.run_statemachine(
                    PlutoPropAssessEvents.ALL_TARGETS_DONE,
                    0
                )
            else:
                # Target maintained. Move to next state.
                return self._smachine.run_statemachine(
                    PlutoPropAssessEvents.INTER_TRIAL_REST_TIMEOUT,
                    0
                )
        return False
    
    def _check_protocol_stop_timeout(self) -> bool:
        _tgterr = self._tgtctrl["final"] - self.pluto.hocdisp
        
        # Target not reached
        if abs(_tgterr) > self._protocol['target_error_th']:
            self._time = 0
            return False
        
        # Target reached
        # Check if the target has been maintained for the required duration.
        if self._time >= self._protocol['intert_rest_dur']:
            # Close trial data file.
            if self._data['trialfhandle'] is not None:
                self._data['trialfhandle'].flush()
                self._data['trialfhandle'].close()
                self._data['trialfile'] = ""
                self._data['trialfhandle'] = None

            # Go to the next trial.
            # All done.
            return self._smachine.run_statemachine(
                PlutoPropAssessEvents.ALL_TARGETS_DONE,
                0
            )
        return False

    #
    # Protocol related functions
    #
    def _are_all_trials_done(self):
        return self._data['trialno'] + 1 == len(self._data['targets'])

    def _goto_next_trial(self):
        # Increment trial number and create new file
        self._data['trialno'] += 1
        # Check if all trials are completed.
        if self._data['trialno'] < len(self._data['targets']):
            self._data['trialfile'] = f"{self.outdir}/propass_trial_{self._data['trialno']+1:02d}.csv"
            self._data['trialfhandle'] = None
            return True
        else:
            return False
    
    def _update_target_position(self):
        _t, _init, _tgt, _dur = (self._tgtctrl["time"],
                                 self._tgtctrl["init"],
                                 self._tgtctrl["final"],
                                 self._tgtctrl["dur"])
        # Limit time to be between 0 and 1.
        self._tgtctrl["curr"] = _init + (_tgt - _init) * clip(_t / _dur)
        # Send command to the robot.
        self.pluto.set_control_target(-self._tgtctrl["curr"] / pdef.HOCScale)
    
    def _update_target_position_mjt(self):
        _t, _init, _tgt, _dur = (self._tgtctrl["time"],
                                 self._tgtctrl["init"],
                                 self._tgtctrl["final"],
                                 self._tgtctrl["dur"])
        # Limit time to be between 0 and 1.
        self._tgtctrl["curr"] = _init + (_tgt - _init) * mjt(clip(_t / _dur))
        # Send command to the robot.
        self.pluto.set_control_target(-self._tgtctrl["curr"] / pdef.HOCScale)

    def _set_position_torque_target_information(self, initpos, finalpos):
        self._tgtctrl["time"] = 0
        # Position
        self._tgtctrl["init"] = initpos
        self._tgtctrl["final"] = finalpos
        self._tgtctrl["curr"] = initpos
        # Duration/Speed
        self._tgtctrl["dur"] = abs(self._tgtctrl["final"] - self._tgtctrl["init"]) / self._protocol['move_speed']
        self._tgtctrl["dur"] = self._tgtctrl["dur"] if self._tgtctrl["dur"] != 0 else 1.0
        self._ctrl_timer.start(int(passdef.PROPASS_CTRL_TIMER_DELTA * 1000))
        # Initialize the propass state machine time
        self._time = -1

    def _create_trial_file(self):
        self._data['trialfhandle'] = open(self._data["trialfile"], "w")
            # Write the header and trial details
        self._data['trialfhandle'].writelines([
                f"subject type: {self._subjtype}\n",
                f"limb: {self._limb}\n",
                f"grip type: {self._griptype}\n",
                f"arom: {self._arom}cm\n",
                f"prom: {self._prom}cm\n",
                f"trial: {self._data['trialno']+1}\n",
                f"target: {self._data['targets'][self._data['trialno']]}cm\n",
                f"start time: {self._data['trial_strt_t'].strftime('%Y-%m-%d %H:%M:%S.%f')}\n",
                "time,status,error,mechanism,angle,hocdisp,torque,control,target,button,framerate,state\n"
            ])
        self._data['trialfhandle'].flush()
    
    #
    # Others
    #
    def _perform_action(self, action: PlutoPropAssessAction) -> None:
        # print(f"Performing action: {action}")
        if action == PlutoPropAssessAction.SET_CONTROl_TO_NONE:
            # Check if the current control type is not NONE.
            if self.pluto.controltype != pdef.ControlType["NONE"]:
                self.pluto.set_control_type("NONE")
        elif action == PlutoPropAssessAction.SET_CONTROL_TO_TORQUE:
            if self.pluto.controltype != pdef.ControlType["TORQUE"]:
                self.pluto.set_control_type("TORQUE")
                self.pluto.set_control_target(target=0, dur=2.0)
        elif action == PlutoPropAssessAction.SET_CONTROL_TO_POSITION:
            if self.pluto.controltype != pdef.ControlType["POSITION"]:
                self.pluto.set_control_type("POSITION")
                self.pluto.set_control_bound(1.0)
                self.pluto.set_control_gain(2.0)
                self.pluto.set_control_target(target=self.pluto.angle, dur=1.0)
        elif action == PlutoPropAssessAction.SET_HAPTIC_DEMO_TARGET_POSITION:
            if self.pluto.target != -self.data.get_current_target() / pdef.HOCScale:
                self.pluto.set_control_target(
                    target=-self.data.get_current_target(False) / pdef.HOCScale,
                    dur=PropConst.DEMO_TGT_REACH_DURATION
                )
                self.pluto.set_control_target(
                    target=-self.data.get_current_target(False) / pdef.HOCScale,
                    dur=PropConst.DEMO_TGT_REACH_DURATION
                )
                self.pluto.set_control_target(
                    target=-self.data.get_current_target(False) / pdef.HOCScale,
                    dur=PropConst.DEMO_TGT_REACH_DURATION
                )
                self.pluto.set_control_target(
                    target=-self.data.get_current_target(False) / pdef.HOCScale,
                    dur=PropConst.DEMO_TGT_REACH_DURATION
                )
                self.pluto.set_control_target(
                    target=-self.data.get_current_target(False) / pdef.HOCScale,
                    dur=PropConst.DEMO_TGT_REACH_DURATION
                )

        # elif action == PlutoPropAssessAction.SET_CONTROL_TO_TORQUE:
        #     # Check if the current control type is not TORQUE.
        #     if self.pluto.controltype != pdef.ControlType["TORQUE"]:
        #         self.pluto.set_control_type("TORQUE")
        #     self.pluto.set_control_target(target=0, dur=2.0)
        # elif action == PlutoPropAssessAction.SET_TORQUE_TARGET_TO_ZERO:
        #     if self.pluto.controltype != pdef.ControlType["TORQUE"]:
        #         self.pluto.set_control_type("TORQUE")
        #     self.pluto.set_control_target(target=0, dur=2.0)
        # elif action == PlutoPropAssessAction.SET_TORQUE_TARGET_TO_DIR:
        #     if self.pluto.controltype != pdef.ControlType["TORQUE"]:
        #         self.pluto.set_control_type("TORQUE")
        #     self.pluto.set_control_target(target=1.0, dur=2.0)
        # elif action == PlutoPropAssessAction.SET_TORQUE_TARGET_TO_OTHER_DIR:
        #     if self.pluto.controltype != pdef.ControlType["TORQUE"]:
        #         self.pluto.set_control_type("TORQUE")
        #     self.pluto.set_control_target(target=-1.0, dur=2.0)
        # Display instruction.
        self.ui.subjInst.setText(self._smachine.instruction)
    
    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               pos=(50, 300))
        self._devdatawnd.show()
    
    #
    # State handler functions
    #
    def _handle_wait_for_start(self, statetrans):
        self._ctrl_timer.stop()
    
    def _handle_wait_for_haptic_display_start(self, statetrans):
        # Go to the next trial if there is a state transition.
        if statetrans:
            _ = self._goto_next_trial()
        self._tgtctrl['time'] = -1
        self._time = -1
        self._ctrl_timer.stop()
    
    def _handle_trial_haptic_display_moving(self, statetrans):
        # Check if timer has been started already.
        if statetrans:
            # Create and open next trial file for data logging.
            self._create_trial_file()

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=self._data['targets'][self._data['trialno']]
            )

            # Set control type and target
            self._pluto.set_control_type("POSITION")
            self._pluto.set_control_target(self._pluto.angle)

    def _handle_trial_haptic_display(self, statetrans):
        # Initialize the statemachine timer if needed.
        if statetrans:
            self._time = 0.
            # Reset the shown position
            self._summary['shownpos'] = []
        # Log data only if the function is called from the new data callback.
        if inspect.stack()[1].function == '_callback_pluto_newdata':
            self._summary['shownpos'].append(self._pluto.hocdisp)
    
    def _handle_intra_trial_rest(self, statetrans):
        # Check if there has been a state transitions. This indicates that we
        # to move the hand back to the closed position.
        if statetrans:
            # Flush data to disk
            self._data['trialfhandle'].flush()

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=0
            )
    
    def _handle_trial_assessment_moving(self, statetrans):
        if statetrans:
            # Beep Beep
            winsound.Beep(BEEP_FREQ, BEEP_DUR)

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=self.prom
            )
    
    def _handle_trial_assessment_response_hold(self, statetrans):
        if statetrans:
            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=self._pluto.hocdisp
            )
            self._time = 0
            # Reset sensed position information in the summary data
            self._summary['sensedpos'] = []
        # Log data only if the function is called from the new data callback.
        if inspect.stack()[1].function == '_callback_pluto_newdata':
            self._summary['sensedpos'].append(self._pluto.hocdisp)
    
    def _handle_trial_assessment_no_response_hold(self, statetrans):
        if statetrans:
            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=self._pluto.hocdisp
            )
            self._time = 0
            # Reset position information in the summary data
            self._summary['pos'] = []
    
    def _handle_inter_trial_rest(self, statetrans):
        if statetrans:
            # Flush data to disk
            self._data['trialfhandle'].flush()

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=0
            )
    
    def _handle_protocol_pause(self, statetrans):
        self._ctrl_timer.stop()
    
    def _handle_protocol_stop(self, statetrans):
        if statetrans:
            # Flush data to disk
            try:
                self._data['trialfhandle'].flush()
            except AttributeError:
                pass

            # Set target information.
            self._set_position_torque_target_information(
                initpos=self._pluto.hocdisp,
                finalpos=0
            )
    
    def _handle_protocol_done(self, statetrans):
        # Stop control.
        self._pluto.set_control_type("NONE")
        self._ctrl_timer.stop()


if __name__ == '__main__':
    import qtjedi
    qtjedi._OUTDEBUG = True
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM13")
    pcalib = PlutoPropAssessWindow(
        plutodev=plutodev, 
        assessinfo={
            "subjid": "",
            "type": "Stroke",
            "limb": "Left",
            "mechanism": "HOC",
            "session": "testing",
            "rawfile": "rawfiletest.csv",
            "summaryfile": "summaryfiletest.csv",
            "arom": [0, 3],
            "prom": [0, 5],
        },
        dataviewer=True,
        heartbeat=False)
    pcalib.show()
    sys.exit(app.exec_())
