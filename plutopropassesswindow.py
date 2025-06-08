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
    QTimer,
    QThread
)
import pyqtgraph as pg

from enum import Enum, auto
from datetime import datetime as dt

import json
import random
import winsound

import plutodefs as pdef
from plutodefs import PlutoEvents as PlEvnts
from ui_plutopropassessctrl import Ui_ProprioceptionAssessWindow
from ui_plutoapromassess import Ui_APRomAssessWindow
from plutodataviewwindow import PlutoDataViewWindow
import plutoassessdef as passdef
import plutofullassessdef as pfadef
from plutoapromwindow import APROMRawDataLoggingState as LogState
import plutoapromwindow as apromwnd
from misc import CSVBufferWriter as CSVWriter

from plutofullassessdef import Proprioception as Prop


# Module level constants
BEEP_FREQ = 2500  # Set Frequency To 2500 Hertz
BEEP_DUR = 1000  # Set Duration To 1000 ms == 1 second


# Some useful lambda functions
del_time = lambda x: dt.now() - (dt.now() if x is None else x) 
increment_time = lambda x : x + passdef.PROPASS_CTRL_TIMER_DELTA if x  >= 0 else -1
clip = lambda x: min(max(0, x), 1)
mjt = lambda x: np.polyval([6, -15, 10, 0, 0, 0], clip(x))


class Events(Enum):
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


class Actions(Enum):
    NO_CTRL = 0
    BEEP = auto()
    POS_CTRL = auto()
    DEMO_MOVE = auto()
    CTRL_HOLD = auto()
    GO_HOME = auto()
    ASSESS_MOVE = auto()
    DO_NOTHING = auto()


class States(Enum):
    DONE = 0
    REST = auto()
    DEMO_WAIT = auto()
    DEMO_MOVING = auto()
    DEMO_HOLDING = auto()
    INTRA_TRIAL_REST = auto()
    ASSESS_MOVING = auto()
    ASSESS_HOLDING = auto()
    ASSESS_NORESPONSE = auto()
    INTER_TRIAL_REST = auto()
    STOP = auto()

    @staticmethod
    def haptic_demo_states():
        return [States.DEMO_WAIT,
                States.DEMO_MOVING,
                States.DEMO_HOLDING]
    

class BeepThread(QThread):
    def __init__(self, frequency=BEEP_FREQ, duration=BEEP_DUR, parent=None):
        super().__init__(parent)
        self.frequency = frequency
        self.duration = duration
        self._play = False
        self._stop = False

    def play(self):
        self._play = True

    def stop(self):
        self._stop = True

    def run(self):
        while not self._stop:
            if self._play:
                winsound.Beep(self.frequency, self.duration)
                self._play = False
            self.msleep(100 + np.random.randint(0, 100))


class PlutoPropAssessData():
    def __init__(self, assessinfo: dict):
        self._assessinfo = assessinfo
        self._demomode = None
        # Trial variables
        self._startpos = None
        self._trialpostorq = {}
        self._buffer = {"dt": [], "pos": [], "vel": [], "ctrl": []}
        # Generate targets.
        self._targets = []
        self._generate_targets()
        self._currtrial = -1
        self._currtarget = None
        self._passdata = [{} for _ in range(len(self._targets))]
        
        # Propprioceptive assessment position
        self._proppostorq = [[] for _ in range(self.ntrials)]
        
        # Logging variables
        self._logstate: LogState = LogState.WAIT_FOR_LOG
        self._rawwriter: CSVWriter = CSVWriter(fname=self.rawfile,
                                               header=Prop.RAW_HEADER)
        self._summwriter: CSVWriter = CSVWriter(fname=self.summaryfile, 
                                                header=Prop.SUMMARY_HEADER,
                                                flush_interval=0.0,
                                                max_rows=1)
    
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
    def current_trial(self):
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
        return self._buffer
    
    @property
    def trialpostorq(self):
        return self._trialpostorq
    
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
        return self._currtrial >= len(self._targets)
    
    @property
    def rawfilewriter(self):
        return self._rawwriter
    
    @property
    def current_target(self):
        return self._currtarget
    
    def start_newtrial(self):
        """Start a new trial.
        """
        if self._currtrial < len(self.targets):
            self._startpos = None
            self._buffer = {"dt": [], "pos": [], "vel": [], "ctrl": []}
            # Update trial number and target
            if self._demomode:
                self._currtrial = 0
                self._currtarget = (0.75 * np.random.rand() + 0.25) * self.prom[1] 
            else:
                self._currtrial = self._currtrial + 1
                self._currtarget = self._targets[self._currtrial] if self._currtrial < len(self._targets) else None
            self._trialpostorq = {
                'startpos': None,
                'tgtpos': self.current_target,
                'shownpos': None,
                'showntorq': None,
                'sensedpos': None,
                'sensedtorq': None,
            }

    def add_newdata(self, dt, pos, ctrl):
        """Add new data to the trial data.
        """
        self._buffer['dt'].append(dt)
        self._buffer['pos'].append(pos)
        self._buffer['vel'].append((pos - self._buffer['pos'][-2]) / dt
                                      if len(self._buffer['pos']) > 1
                                      else 0)
        self._buffer['ctrl'].append(ctrl)
        if len(self._buffer['dt']) > pfadef.POS_VEL_WINDOW_LENGHT:
            self._buffer['dt'].pop(0)
            self._buffer['pos'].pop(0)
            self._buffer['vel'].pop(0)
            self._buffer['ctrl'].pop(0)
    
    def set_prop_assessment(self):
        """Set the proprioceptive assessment value for the given trial.
        """
        # Update ROM 
        self._passdata[self._currtrial] = self._trialpostorq.copy()
        # Update the summary file.
        self._summwriter.write_row([
            self.session,
            self.type,
            self.limb,
            self.mechanism,
            self.current_trial,
            self._trialpostorq['startpos'],
            self.arom[0], self.arom[1],
            self.prom[0], self.prom[1],
            self.current_target,
            self._trialpostorq['shownpos'],
            self._trialpostorq['sensedpos'],
            self._trialpostorq['showntorq'],
            self._trialpostorq['sensedtorq']
        ])
        
    def set_startpos(self):
        """Sets the start position as the average of trial data.
        """
        self._startpos = float(np.mean(self._buffer['pos']))
        self._trialpostorq['startpos'] = self._startpos
        self._trialpostorq['tgtpos'] = self.current_target
    
    def set_shownpostorq(self):
        """
        """
        self._trialpostorq['shownpos'] = float(np.mean(self._buffer['pos']))
        self._trialpostorq['showntorq'] = float(np.mean(self._buffer['ctrl']))
    
    def set_sensedpostorq(self, success=True):
        """
        """
        self._trialpostorq['sensedpos'] = (self.prom[1] if not success 
                                           else float(np.mean(self._buffer['pos'])))
        self._trialpostorq['sensedtorq'] = float(np.mean(self._buffer['ctrl']))
        
    def start_rawlogging(self):
        self._logstate = LogState.LOG_DATA
    
    def terminate_rawlogging(self):
        self._logstate = LogState.LOGGING_DONE
        if self._rawwriter:
            self._rawwriter.close()
            self._rawwriter = None
    
    def terminate_summarylogging(self):
        if self._summwriter:
            self._summwriter.close()
            self._summwriter = None
    
    def _generate_targets(self):
        _tgtsep = Prop.TGT_POSITIONS[0] * self.prom[1]
        _tgts = (Prop.TGT_POSITIONS
                 if _tgtsep >= Prop.MIN_TGT_SEP
                 else Prop.TGT_POSITIONS[1:2])
        # Generate the randomly order targets
        _tgts = Prop.NO_OF_TRIALS * _tgts
        random.shuffle(_tgts)
        self._targets = (self.prom[1] * np.array(_tgts)).tolist()
    
    def _get_trial_details_line(self, demomode=False, state="Haptic Demo"):
        # In demo mode.
        if demomode:
            pass
        # Not in demo mode.
        _dispstr = [
            "Trial: " + 
            f"{self.current_trial:3d} / {self.ntrials:3d}"
            if self.current_trial > 0
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
        self._state = States.REST
        self._instruction = "Press the Start Button to start assessment."
        self._statetimer = 0
        self._data = data
        self._instruction = f""
        self._instdisp = instdisp
        self._pluto = plutodev
        self._beeper = BeepThread()
        self._beeper.start()
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._statehandlers = {
            States.REST: self._handle_rest,
            States.DEMO_WAIT: self._handle_demo_wait,
            States.DEMO_MOVING: self._handle_demo_moving,
            States.DEMO_HOLDING: self._handle_demo_holding,
            States.INTRA_TRIAL_REST: self._handle_intra_trial_rest,
            States.ASSESS_MOVING: self._handle_assess_moving,
            States.ASSESS_HOLDING: self._handle_assess_holding,
            States.ASSESS_NORESPONSE: self._handle_assess_noresponse,
            States.INTER_TRIAL_REST: self._handle_inter_trial_rest,
            States.STOP: self._handle_stop,
            States.DONE: self._handle_done
        }
        # Instructions.
        self._stateinstructions = {
            States.REST: "Close Hand & press button to start.",
            States.DEMO_WAIT: "Waiting for Haptic Display to start.",
            States.DEMO_MOVING: "Haptic Display Moving.",
            States.DEMO_HOLDING: "Haptic Display Holding.",
            States.INTRA_TRIAL_REST: "Intra Trial Rest.",
            States.ASSESS_MOVING: "Trial Assessment Moving. ",
            States.ASSESS_HOLDING: "Trial Assessment Response Holding.",
            States.ASSESS_NORESPONSE: "Trial Assessment No Response Holding.",
            States.INTER_TRIAL_REST: "Inter Trial Rest.",
            States.STOP: "Protocol Stopped. Press Start to continue.",
            States.DONE: "Proprioceptive Assessment Done."
        }
        # Action handlers
        self._actionhandlers = {
            Actions.NO_CTRL: self._act_no_ctrl, 
            Actions.BEEP: self._act_beep,
            Actions.POS_CTRL: self._act_pos_ctrl, 
            Actions.DEMO_MOVE: self._act_demo_move, 
            Actions.CTRL_HOLD: self._act_ctrl_hold, 
            Actions.GO_HOME: self._act_go_home, 
            Actions.ASSESS_MOVE: self._act_assess_move, 
            Actions.DO_NOTHING: self._act_do_nothing, 
        }
        # Start a new trial.
        self._data.start_newtrial()

        # Defining a few useful lambda functions.
        self._define_me_some_lambdas()
    
    @property
    def state(self):
        return self._state
    
    @property
    def instruction(self):
        return self._instruction
    
    @property
    def addn_info(self):
        return self._addn_info
    
    def run_statemachine(self, event, dt):
        """Execute the state machine depending on the given even that has occured.
        """
        _action = self._statehandlers[self._state](event, dt)
        self._actionhandlers[_action]()
        # Display instructions.
        self._display_instruction()

    def _handle_rest(self, event, dt) -> Actions:
        """Waits till the start button is pressed.
        """
        # Check if all trials are done.
        if not self._data.demomode and self._data.all_trials_done:
            self._data.terminate_rawlogging()
            self._data.terminate_summarylogging()
            if event == PlEvnts.RELEASED:
                self._state = States.DONE
                self._statetimer = None
            return Actions.NO_CTRL
        # Check if all trials are done or if we are in the demo mode.
        if event == PlEvnts.RELEASED:
            # Check to make sure the angle is close to zero.
            if self._pluto.hocdisp < Prop.START_POSITION_TH:
                self._data.set_startpos()
                self._state = States.DEMO_WAIT
                self._statetimer = 0.5
                if not self._data.demomode:
                    self._data.start_rawlogging()
                return Actions.POS_CTRL
        return Actions.NO_CTRL

    def _handle_demo_wait(self, event, dt) -> Actions:
        if event == PlEvnts.NEWDATA:
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._state = States.DEMO_MOVING
                return Actions.BEEP
        return Actions.POS_CTRL

    def _handle_demo_moving(self, event, dt) -> Actions:
        if event == PlEvnts.NEWDATA:
            # Check if the target has been reached and the subject is holding.
            if self.subj_in_target():
                self._state = States.DEMO_HOLDING
                return Actions.CTRL_HOLD
        return Actions.DEMO_MOVE

    def _handle_demo_holding(self, event, dt) -> Actions:
        if event == PlEvnts.NEWDATA:
            if not (self.subj_in_target() and self.subj_is_holding()):
                self._statetimer = Prop.DEMO_DURATION
                return Actions.CTRL_HOLD
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._data.set_shownpostorq()
                self._state = States.INTRA_TRIAL_REST
                self._statetimer = Prop.INTRA_TRIAL_REST_DURATION
                return Actions.CTRL_HOLD
        return Actions.CTRL_HOLD

    def _handle_intra_trial_rest(self, event, dt) -> Actions:
        if event == PlEvnts.NEWDATA:
            if not (self.subj_near_start_position() and self.subj_is_holding()):
                return Actions.GO_HOME
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._state = States.ASSESS_MOVING
                self._statetimer = None
                return Actions.BEEP
        return Actions.GO_HOME
    
    def _handle_assess_moving(self, event, dt) -> Actions:
        if event == PlEvnts.RELEASED:
            self._state = States.ASSESS_HOLDING
            self._statetimer = 1.0
            return Actions.CTRL_HOLD
        if event == PlEvnts.NEWDATA:
            if self.subj_near_prom():
                self._state = States.ASSESS_NORESPONSE
                self._statetimer = 1.0
                return Actions.CTRL_HOLD
        return Actions.ASSESS_MOVE
    
    def _handle_assess_holding(self, event, dt) -> Actions:
        if event == PlEvnts.NEWDATA:
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._data.set_sensedpostorq()
                self._state = States.INTER_TRIAL_REST
                self._statetimer = Prop.INTER_TRIAL_REST_DURATION
                return Actions.GO_HOME
        return Actions.CTRL_HOLD

    def _handle_assess_noresponse(self, event, dt) -> Actions:
        if event == PlEvnts.NEWDATA:
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._data.set_sensedpostorq(success=False)
                self._state = States.INTER_TRIAL_REST
                self._statetimer = Prop.INTER_TRIAL_REST_DURATION
                return Actions.GO_HOME
        return Actions.GO_HOME

    def _handle_inter_trial_rest(self, event, dt) -> Actions:
        if event == PlEvnts.NEWDATA:
            if not self.subj_near_start_position():
                self._statetimer = Prop.INTER_TRIAL_REST_DURATION
                return Actions.GO_HOME
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._data.set_prop_assessment()
                self._data.start_newtrial()
                self._state = States.REST
                self._statetimer = None
                return Actions.GO_HOME
        return Actions.GO_HOME
    
    def _protocol_pause(self, event, dt) -> Actions:
        return False

    def _handle_stop(self, event, dt) -> Actions:
        if event == Events.ALL_TARGETS_DONE:
            self._addn_info = False
            self._state = States.DONE
            return True
        return False

    def _handle_done(self, event, dt) -> Actions:
        return False
    
    #
    # Action handlers
    #
    def _act_no_ctrl(self):
        if self._ctrl_is_none(): return
        self._pluto.set_control_type("NONE")
    
    def _act_beep(self):
        self._beeper.play()

    def _act_pos_ctrl(self):
        if self._ctrl_is_pos(): return
        # Set up position controls
        self._pluto.set_control_type("POSITIONLINEAR")
        self._pluto.set_control_bound(1.0)
        self._pluto.set_control_gain(2.0)
        self._act_demo_move()

    def _act_demo_move(self):        
        # Set the target.
        _tgtdetails = self._compute_target_details(self._data.current_target, demomode=True)
        if self._tgt_set(_tgtdetails["target"]): return
        self._pluto.set_control_target(**_tgtdetails)

    def _act_ctrl_hold(self):
        if self._ctrl_hold(): return
        self._pluto.hold_control()

    def _act_go_home(self):
        if self._ctrl_decay(): return
        self._pluto.decay_control()

    def _act_assess_move(self):
        # Set the target.
        _tgtdetails = self._compute_target_details(self._data.prom[1], demomode=False)
        if self._tgt_set(_tgtdetails["target"]): return
        self._pluto.set_control_target(**_tgtdetails)

    def _act_do_nothing(self):
        pass
    
    def _display_instruction(self):
        if self._state != States.REST:
            self._instdisp.setText(self._stateinstructions[self._state] 
                                + f" [{self._statetimer:1.1f}s]" if self._statetimer else "")
        else:
            if self._data.demomode:
                self._instdisp.setText(f"Press the PLUTO button to start demo trial.")
            elif self._data.all_trials_done:
                self._instdisp.setText(f"All trials done. Press the PLUTO button to quit.")
            else:
                self._instdisp.setText(f"PLUTO button to start trial {self._data.current_trial + 1} / {len(self._data.targets)}.")
    
    #
    # Supporting functions
    #
    def _define_me_some_lambdas(self):
        self._ctrl_is_none = lambda : self._pluto.controltype == pdef.ControlTypes["NONE"]
        self._ctrl_is_pos = lambda : self._pluto.controltype == pdef.ControlTypes["POSITIONLINEAR"]
        self._tgt_set= lambda tgt : np.isclose(self._pluto.target, tgt, rtol=1e-03, atol=1e-03)
        self._ctrl_hold = lambda : self._pluto.controlhold == pdef.ControlHoldTypes["HOLD"]
        self._ctrl_decay = lambda : self._pluto.controlhold == pdef.ControlHoldTypes["DECAY"]
        self.subj_in_target = lambda : np.abs(self._data.current_target - self._pluto.hocdisp) < Prop.TGT_ERR_TH
        self.subj_near_start_position = lambda : self._pluto.hocdisp - self._data.startpos < Prop.TGT_ERR_TH
        self.subj_near_prom = lambda : np.abs(self._pluto.hocdisp - self._data.prom[1]) < Prop.TGT_ERR_TH

    def subj_is_holding(self):
        """Check if the subject is holding the position.
        """
        _th = (pfadef.VEL_HOC_THRESHOLD
               if self._data.mechanism == "HOC"
               else pfadef.VEL_NOT_HOC_THRESHOLD)
        return bool(np.all(np.abs(self._data.trialdata['vel']) < _th))
    
    def _compute_target_details(self, tgtpos, demomode=False) -> dict:
        """Compute the target details for the given target position.
        """
        _initpos = self._pluto.angle
        _finalpos = - tgtpos / pdef.HOCScale - 4 if tgtpos != 0  else 0
        _strtt = 0
        _speed = (1 if not demomode else (2.0 + np.random.rand())) * Prop.MOVE_SPEED
        _dur = float(np.abs(tgtpos - pdef.HOCScale * np.abs(_initpos)) / _speed)
        return {
            "target": _finalpos,
            "target0": _initpos,
            "t0": _strtt,
            "dur": _dur
        }


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
            self.on_close_callback(data={"done": self.data.all_trials_done})
        # Set device to no control.
        self.pluto.set_control_type("NONE")
        # Detach PLUTO callbacks.
        self._detach_pluto_callbacks()
        try:
            self._devdatawnd.close()
        except:
            pass
        self._smachine._beeper.stop()
        return super().closeEvent(event)

    #
    # Update UI
    #
    def update_ui(self):
        # Demo run checkbox
        if self.ui.cbTrialRun.isEnabled():
            _cond1 = self.data.demomode is False
            _cond2 = (self.data.demomode is None
                      and self._smachine.state == States.DEMO_WAIT)
            if _cond1 or _cond2:
                self.ui.cbTrialRun.setEnabled(False)

        # Update current hand position
        if self.pluto.hocdisp is None:
            return
        
        # Update the graph display
        self._update_graph()

        # Update based on state
        _dispstr = [f"Hand Aperture: {self._pluto.hocdisp:5.2f}cm"]
        if self._smachine.state == States.REST:
            pass
        elif self._smachine.state == States.DEMO_WAIT:
            _dispstr += self.data._get_trial_details_line(demomode=False, state="Haptic Demo")
        elif self._smachine.state == States.DEMO_MOVING:
            _dispstr += self.data._get_trial_details_line(demomode=False, state="Haptic Demo")
        # Update text.
        self.ui.lblTitle.setText(" | ".join(_dispstr))

        # Update status message
        self.ui.lblStatus.setText(f"{self.pluto.error} | {self.pluto.controltype} | {self._smachine.state}")

        # Close if needed
        if self._smachine.state == States.DONE:
            self.close()

    def _update_graph(self):
        # Current position.
        self.ui.currPosLine1.setData([self.pluto.hocdisp, self.pluto.hocdisp],
                                     [-40, 15])
        self.ui.currPosLine2.setData([-self.pluto.hocdisp, -self.pluto.hocdisp],
                                     [-40, 15])
        # Target line
        if self._smachine.state in States.haptic_demo_states():
            _tgtpos = self.data.current_target
            if _tgtpos:
                self.ui.tgtLine1.setData([_tgtpos, _tgtpos], [-40, 15])
                self.ui.tgtLine2.setData([-_tgtpos, -_tgtpos], [-40, 15])
        else:
            self.ui.tgtLine1.setData([0, 0], [0, 0])
            self.ui.tgtLine2.setData([0, 0], [0, 0])
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
        _whtpen = pg.mkPen(color = '#FFFFFF',width=1)
        self.ui.currPosLine1 = pg.PlotDataItem([0, 0], [-40, 15], pen=_whtpen)
        self.ui.currPosLine2 = pg.PlotDataItem([0, 0], [-40, 15], pen=_whtpen)
        _pgobj.addItem(self.ui.currPosLine1)
        _pgobj.addItem(self.ui.currPosLine2)
        
        # AROM Lines
        _redpendot = pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        self.ui.aromLine1 = pg.PlotDataItem([self.data.arom[1], self.data.arom[1]],
                                            [-40, 15], pen=_redpendot)
        self.ui.aromLine2 = pg.PlotDataItem([-self.data.arom[1], -self.data.arom[1]],
                                            [-40, 15], pen=_redpendot)
        _pgobj.addItem(self.ui.aromLine1)
        _pgobj.addItem(self.ui.aromLine2)
        
        # PROM Lines
        _blupendot = pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        self.ui.promLine1 = pg.PlotDataItem([self.data.prom[1], self.data.prom[1]],
                                            [-40, 15], pen=_blupendot)
        self.ui.promLine2 = pg.PlotDataItem([-self.data.prom[1], -self.data.prom[1]],
                                            [-40, 15], pen=_blupendot)
        _pgobj.addItem(self.ui.promLine1)
        _pgobj.addItem(self.ui.promLine2)
        
        # Target Lines
        _grnpen = pg.mkPen(color = '#00FF00',width=2)
        self.ui.tgtLine1 = pg.PlotDataItem([0, 0], [-40, 15], pen=_grnpen)
        self.ui.tgtLine2 = pg.PlotDataItem([0, 0], [-40, 15], pen=_grnpen)
        _pgobj.addItem(self.ui.tgtLine1)
        _pgobj.addItem(self.ui.tgtLine2)

        # Instruction text
        _font = QtGui.QFont("Cascadia Mono Light", 14)
        self.ui.subjInst = pg.TextItem(text='', color='w', anchor=(0.5, 0.5))
        self.ui.subjInst.setPos(0, 30)  # Set position (x, y)
        # Set font and size
        self.ui.subjInst.setFont(_font)
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
        # Update trial data.
        self.data.add_newdata(
            dt=self.pluto.delt(),
            pos=self.pluto.hocdisp if self.data.mechanism == "HOC" else self.pluto.angle,
            ctrl=self.pluto.control
        )
        # Run the statemachine
        self._smachine.run_statemachine(
            PlEvnts.NEWDATA,
            self.pluto.delt()
        )
        if np.random.rand() < 0.2:
            self.update_ui()
        
        #
        # Log data
        if self.data.logstate == LogState.LOG_DATA:
            self.data.rawfilewriter.write_row([
                self.pluto.systime, self.pluto.currt, self.pluto.packetnumber,
                self.pluto.status, self.pluto.controltype, self.pluto.error, 
                self.pluto.limb, self.pluto.mechanism,
                self.pluto.angle, self.pluto.hocdisp, self.pluto.torque, 
                self.pluto.control, self.pluto.target, self.pluto.desired,
                self.pluto.controlbound, self.pluto.controldir, 
                self.pluto.controlgain, self.pluto.controlhold, self.pluto.button,
                self.data.current_trial,
                f"{self._smachine.state.name}"
            ])

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        _action = self._smachine.run_statemachine(
            PlEvnts.RELEASED,
            self.pluto.delt()
        )
        self.update_ui()

    #
    # Control Callbacks
    #
    
    #
    # Others
    #
    # def _perform_action(self, action: Actions) -> None:
    #     if action == Actions.NO_CTRL:
    #         # Check if the current control type is not NONE.
    #         if self.pluto.controltype != pdef.ControlTypes["NONE"]:
    #             self.pluto.set_control_type("NONE")
    #     elif action == Actions.POS_CTRL:
    #         if self.pluto.controltype != pdef.ControlTypes["POSITIONLINEAR"]:
    #             self.pluto.set_control_type("POSITIONLINEAR")
    #             self.pluto.set_control_bound(1.0)
    #             self.pluto.set_control_gain(2.0)
    #             # Set the assessment torque targets.
    #             _tgtdetails = self._compute_target_details(self.data.current_target, demomode=True)
    #             if self.pluto.target != _tgtdetails["target"]:
    #                 self.pluto.set_control_target(**_tgtdetails)
    #     elif action == Actions.DEMO_MOVE:
    #         _tgtdetails = self._compute_target_details(self.data.current_target, demomode=True)
    #         _tgtset = np.isclose(self.pluto.target, _tgtdetails["target"], rtol=1e-03, atol=1e-03)
    #         if np.random.rand() < 0.1 and not _tgtset:
    #             self.pluto.set_control_target(**_tgtdetails)
    #     elif action == Actions.CTRL_HOLD:
    #         if self.pluto.controlhold != pdef.ControlHoldTypes["HOLD"]:
    #             self.pluto.hold_control()
    #     elif action == Actions.GO_HOME:
    #         if self.pluto.controlhold != pdef.ControlHoldTypes["DECAY"]:
    #             self.pluto.decay_control()
    #     elif action == Actions.ASSESS_MOVE:
    #         # Set the assessment torque targets.
    #         _tgtdetails = self._compute_target_details(self.data.prom[1])
    #         _tgtset = np.isclose(self.pluto.target, _tgtdetails["target"], rtol=1e-03, atol=1e-03)
    #         if np.random.rand() < 0.1 and not _tgtset:
    #             self.pluto.set_control_target(**_tgtdetails)
    #     elif action == Actions.CTRL_HOLD:
    #         # Set the assessment torque targets.
    #         _tgtdetails = self._compute_target_details(self.data.trialpostorq["holdtgt"], intantaneous=True)
    #         _tgtset = np.isclose(self.pluto.target, _tgtdetails["target"], rtol=1e-03, atol=1e-03)
    #         if np.random.rand() < 0.1 and not _tgtset:
    #             self.pluto.set_control_target(**_tgtdetails)

    #     # elif action == Actions.SET_CONTROL_TO_TORQUE:
    #     #     # Check if the current control type is not TORQUE.
    #     #     if self.pluto.controltype != pdef.ControlTypes["TORQUE"]:
    #     #         self.pluto.set_control_type("TORQUE")
    #     #     self.pluto.set_control_target(target=0, dur=2.0)
    #     # elif action == Actions.SET_TORQUE_TARGET_TO_ZERO:
    #     #     if self.pluto.controltype != pdef.ControlTypes["TORQUE"]:
    #     #         self.pluto.set_control_type("TORQUE")
    #     #     self.pluto.set_control_target(target=0, dur=2.0)
    #     # elif action == Actions.SET_TORQUE_TARGET_TO_DIR:
    #     #     if self.pluto.controltype != pdef.ControlTypes["TORQUE"]:
    #     #         self.pluto.set_control_type("TORQUE")
    #     #     self.pluto.set_control_target(target=1.0, dur=2.0)
    #     # elif action == Actions.SET_TORQUE_TARGET_TO_OTHER_DIR:
    #     #     if self.pluto.controltype != pdef.ControlTypes["TORQUE"]:
    #     #         self.pluto.set_control_type("TORQUE")
    #     #     self.pluto.set_control_target(target=-1.0, dur=2.0)
    #     # Display instruction.
    #     self.ui.subjInst.setText(self._smachine.instruction)
    

    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               pos=(50, 300))
        self._devdatawnd.show()


if __name__ == '__main__':
    import qtjedi
    qtjedi._OUTDEBUG = False
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
