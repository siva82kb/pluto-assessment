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
    
    @property
    def current_target(self):
        """Get the current target position for the trial.
        """
        # Check if in demomode.
        if self._demomode is True:
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
            f"{self.current_target:5.1f}cm"
            if self.current_target is not None
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
                self._data.set_startpos()
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

    def _trial_haptic_display(self, event, dt) -> PlutoPropAssessAction:
        if event == pdef.PlutoEvents.NEWDATA:
            # Check if the target has been reached and the subject is holding.
            if not (self.subj_in_target() and self.subj_is_holding()):
                self._statetimer = PropConst.DEMO_DURATION
                return PlutoPropAssessAction.SET_HAPTIC_DEMO_TARGET_POSITION
            # Target has been reached.
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._state = PlutoPropAssessStates.INTRA_TRIAL_REST
                self._statetimer = PropConst.INTRA_TRIAL_REST_DURATION
                return PlutoPropAssessAction.SET_HOME_POSITION
            self._instruction = "Target Reached. Hold the position."
        return PlutoPropAssessAction.SET_HAPTIC_DEMO_TARGET_POSITION

    def _intra_trial_rest(self, event, dt) -> PlutoPropAssessAction:
        if event == pdef.PlutoEvents.NEWDATA:
            if not (self.subj_near_start_position() and self.subj_is_holding()):
                return PlutoPropAssessAction.SET_HOME_POSITION
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._state = PlutoPropAssessStates.TRIAL_ASSESSMENT_MOVING
                self._instruction = "Starting Trial Assessment. Relax." 
                return PlutoPropAssessAction.SET_ASSESSMENT_TARGET_POSITION
        return PlutoPropAssessAction.SET_HOME_POSITION
    
    def _trial_assessment_moving(self, event, dt) -> PlutoPropAssessAction:
        return PlutoPropAssessAction.SET_ASSESSMENT_TARGET_POSITION

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
        return np.abs(self._data.current_target - self._pluto.hocdisp) < PropConst.TGT_ERR_TH
    
    def subj_near_start_position(self) -> bool:
        """Check if the subejct is close to the target position.
        """
        return self._pluto.hocdisp - self._data.startpos < PropConst.TGT_ERR_TH


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

        self.on_close_callback = onclosecb
        
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
            self.on_close_callback(data=[])
        # Set device to no control.
        self.pluto.set_control_type("NONE")
        # Detach PLUTO callbacks.
        self._detach_pluto_callbacks()
        try:
            self._devdatawnd.close()
        except:
            pass
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
        # Update text.
        self.ui.lblTitle.setText(" | ".join(_dispstr))
        # self.ui.textInformation.setText("\n".join(_dispstr))

        # Update status message
        self.ui.lblStatus.setText(f"{self.pluto.error} | {self.pluto.controltype} | {self._smachine.state}")

    def _update_graph(self):
        # Current position.
        self.ui.currPosLine1.setData(
            [self.pluto.hocdisp, self.pluto.hocdisp],
            [-40, 15]
        )
        self.ui.currPosLine2.setData(
            [-self.pluto.hocdisp, -self.pluto.hocdisp],
            [-40, 15]
        )
        # Update target position when needed.
        _checkstate = not (
            self._smachine.state == PlutoPropAssessStates.FREE_RUNNING
            or self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING
            or self._smachine.state == PlutoPropAssessStates.INTER_TRIAL_REST
            or self._smachine.state == PlutoPropAssessStates.PROTOCOL_STOP
            or self._smachine.state == PlutoPropAssessStates.PROP_DONE
        )
        _tgt = self.data.current_target if _checkstate else 0
        # Update target line        
        self.ui.tgtLine1.setData(
            [_tgt, _tgt],
            [-40, 15]
        )
        self.ui.tgtLine2.setData(
            [-_tgt, -_tgt],
            [-40, 15]
        )
        # Update target instruction text
        if self._smachine.state == PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            _tgtstr = f"Hold {self._smachine._statetimer:+1.1f}"
            self.ui.tgt1Inst.setPos(self.data.current_target, 20)
            self.ui.tgt1Inst.setText(_tgtstr)
            self.ui.tgt2Inst.setPos(-self.data.current_target, 20)
            self.ui.tgt2Inst.setText(_tgtstr)
        elif self._smachine.state == PlutoPropAssessStates.INTRA_TRIAL_REST:
            _tgtstr = f"Hold {self._smachine._statetimer:+1.1f}"
            self.ui.tgt1Inst.setPos(0, 20)
            self.ui.tgt1Inst.setText(_tgtstr)
            self.ui.tgt2Inst.setText("")

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
            [-40, 15],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        self.ui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [-40, 15],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        _pgobj.addItem(self.ui.currPosLine1)
        _pgobj.addItem(self.ui.currPosLine2)
        
        # AROM Lines
        self.ui.aromLine1 = pg.PlotDataItem(
            [self.data.arom[1], self.data.arom[1]],
            [-40, 15],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        self.ui.aromLine2 = pg.PlotDataItem(
            [-self.data.arom[1], -self.data.arom[1]],
            [-40, 15],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self.ui.aromLine1)
        _pgobj.addItem(self.ui.aromLine2)
        
        # PROM Lines
        self.ui.promLine1 = pg.PlotDataItem(
            [self.data.prom[1], self.data.prom[1]],
            [-40, 15],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        self.ui.promLine2 = pg.PlotDataItem(
            [-self.data.prom[1], -self.data.prom[1]],
            [-40, 15],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self.ui.promLine1)
        _pgobj.addItem(self.ui.promLine2)
        
        # Target Lines
        self.ui.tgtLine1 = pg.PlotDataItem(
            [0, 0],
            [-40, 15],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        self.ui.tgtLine2 = pg.PlotDataItem(
            [0, 0],
            [-40, 15],
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
        
        # target instruction.
        # tgt 1
        self.ui.tgt1Inst = pg.TextItem(text='', color='w', anchor=(0.5, 0.5))
        self.ui.tgt1Inst.setPos(0, 0)  # Set position (x, y)
        # Set font and size
        self.ui.tgt1Inst.setFont(QtGui.QFont("Cascadia Mono Light", 8))
        _pgobj.addItem(self.ui.tgt1Inst) 
        # tgt 2
        self.ui.tgt2Inst = pg.TextItem(text='', color='w', anchor=(0.5, 0.5))
        self.ui.tgt2Inst.setPos(0, 0)  # Set position (x, y)
        # Set font and size
        self.ui.tgt2Inst.setFont(QtGui.QFont("Cascadia Mono Light", 8))
        _pgobj.addItem(self.ui.tgt2Inst)

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
        # Update trial data.
        self.data.add_newdata(
            dt=self.pluto.delt(),
            pos=self.pluto.hocdisp if self.data.mechanism == "HOC" else self.pluto.angle
        )
        # Run the statemachine
        _action = self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA,
            self.pluto.delt()
        )
        self._perform_action(_action)
        if np.random.rand() < 0.1 or _action != PlutoPropAssessAction.DO_NOTHING:
            self.update_ui()

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        _action = self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED,
            self.pluto.delt()
        )
        self._perform_action(_action)
        if _action != PlutoPropAssessAction.DO_NOTHING:
            self.update_ui()

    #
    # Control Callbacks
    #
    
    #
    # Others
    #
    def _perform_action(self, action: PlutoPropAssessAction) -> None:
        if action == PlutoPropAssessAction.SET_CONTROl_TO_NONE:
            # Check if the current control type is not NONE.
            if self.pluto.controltype != pdef.ControlType["NONE"]:
                self.pluto.set_control_type("NONE")
        elif action == PlutoPropAssessAction.SET_CONTROL_TO_POSITION:
            if self.pluto.controltype != pdef.ControlType["POSITIONLINEAR"]:
                self.pluto.set_control_type("POSITIONLINEAR")
                self.pluto.set_control_bound(1.0)
                self.pluto.set_control_gain(2.0)
                # Set the assessment torque targets.
                _tgtdetails = self._compute_target_details(self.data.current_target)
                if self.pluto.target != _tgtdetails["target"]:
                    self.pluto.set_control_target(**_tgtdetails)
        elif action == PlutoPropAssessAction.SET_HAPTIC_DEMO_TARGET_POSITION:
            _tgtdetails = self._compute_target_details(self.data.current_target)
            _tgtset = np.isclose(self.pluto.target, _tgtdetails["target"], rtol=1e-03, atol=1e-03)
            if np.random.rand() < 0.1 and not _tgtset:
                self.pluto.set_control_target(**_tgtdetails)
        elif action == PlutoPropAssessAction.SET_HOME_POSITION:
            # Set the home position.
            _tgtdetails = self._compute_target_details(0)
            if np.random.rand() < 0.1 and self.pluto.target != 0:
                print(_tgtdetails)
                self.pluto.set_control_target(**_tgtdetails)
        elif action == PlutoPropAssessAction.SET_ASSESSMENT_TARGET_POSITION:
            # Set the assessment torque targets.
            _tgtdetails = self._compute_target_details(self.data.current_target)
            _tgtset = np.isclose(self.pluto.target, _tgtdetails["target"], rtol=1e-03, atol=1e-03)
            if np.random.rand() < 0.1 and not _tgtset:
                self.pluto.set_control_target(**_tgtdetails)

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
    
    def _compute_target_details(self, tgtpos, demomode=False) -> dict:
        """Compute the target details for the given target position.
        """
        _initpos = self.pluto.angle
        _finalpos = - tgtpos / pdef.HOCScale - 4
        _strtt = 0
        _speed = (PropConst.MOVE_SPEED
                  if not demomode
                  else (1.5 + np.random.rand()) * PropConst.DEMO_MOVE_SPEED)
        _dur = float(np.abs(tgtpos - pdef.HOCScale * np.abs(_initpos)) / _speed)
        return {
            "target": _finalpos,
            "target0": _initpos,
            "t0": _strtt,
            "dur": _dur
        }

    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               pos=(50, 300))
        self._devdatawnd.show()


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
        heartbeat=False,
        onclosecb=lambda data: print("Done.")
    )
    pcalib.show()
    sys.exit(app.exec_())
