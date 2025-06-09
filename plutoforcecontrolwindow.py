"""
Module for handling the operation of the PLUTO foprce control task.

Author: Sivakumar Balasubramanian
Date: 06 June 2025
Email: siva82kb@gmail.com
"""


import sys
import numpy as np

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,
    QtGui)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtWidgets import QGraphicsEllipseItem
from PyQt5.QtCore import pyqtSignal
import pyqtgraph as pg
from enum import Enum, auto

import misc
import plutodefs as pdef
from plutodefs import PlutoEvents as PlEvnts
import plutofullassessdef as pfadef
from plutofullassessdef import ForceControl
from plutofullassessdef import ForceControl as FCtrl
from ui_plutoapromassess import Ui_APRomAssessWindow
from myqt import CommentDialog
from plutodataviewwindow import PlutoDataViewWindow
from plutoapromwindow import RawDataLoggingState as LogState


class States(Enum):
    REST = 0
    WAIT_START = auto()
    HOLDING = auto()
    NOT_HOLDING = auto()
    CRUSHING = auto()
    RELAX = auto()
    DONE = auto()


class Actions(Enum):
    NO_CONTROL = 0
    SIM_OBJECT = auto()
    DISSOLVE_OBJECT = auto()
    DO_NOTHING = auto()


class PlutoForceControlData(object):
    def __init__(self, assessinfo: dict):
        self._assessinfo = assessinfo
        self._demomode = None
        # Trial variables
        self._currtrial = 0
        self._startpos = None
        self._trialdata = {"dt": [], "pos": [], "vel": []}
        self._currtrial = -1
        self._objparams = self._compute_object_params()
        # Logging variables
        self._logstate: LogState = LogState.WAIT_FOR_LOG
        self._rawwriter: misc.CSVBufferWriter = misc.CSVBufferWriter(
            self.rawfile, 
            header=FCtrl.RAW_HEADER
        )
        self._summwriter: misc.CSVBufferWriter = misc.CSVBufferWriter(
            self.summaryfile, 
            header=FCtrl.SUMMARY_HEADER,
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
    def current_trial(self):
        return self._currtrial
    
    @property
    def session(self):
        return self._assessinfo['session']

    @property
    def ntrials(self):
        return self._assessinfo['ntrials']
    
    @property
    def object_params(self):
        return self._objparams
    
    @property
    def target(self):
        return self.arom[1] * FCtrl.TGT_POSITION
    
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
    def currtrial(self):
        return self._currtrial
    
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
        return self._rawwriter
    
    def start_newtrial(self, reset: bool = False):
        """Start a new trial.
        """
        if self._currtrial < self.ntrials:
            self._trialdata = {"dt": [], "pos": [], "vel": []}
            self._currtrial = 0 if reset else self._currtrial + 1

    def trial_done(self):
        self._summwriter.write_row([
            self.session,
            self.type,
            self.limb,
            self.mechanism,
            self.current_trial,
            self.arom[0],
            self.arom[1],
            self.target,
            FCtrl.TGT_FORCE - FCtrl.TGT_FORCE_WIDTH,
            FCtrl.TGT_FORCE + FCtrl.TGT_FORCE_WIDTH,
        ])

    def add_newdata(self, dt, pos):
        """Add new data to the trial data.
        """
        self._trialdata['dt'].append(dt)
        self._trialdata['pos'].append(pos)
        self._trialdata['vel'].append((pos - self._trialdata['pos'][-2]) / dt
                                      if len(self._trialdata['pos']) > 1
                                      else 0)
        if len(self._trialdata['dt']) > ForceControl.POS_VEL_WINDOW_LENGHT:
            self._trialdata['dt'].pop(0)
            self._trialdata['pos'].pop(0)
            self._trialdata['vel'].pop(0)
    
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

    def _compute_object_params(self):
        # Compute the target parameters.
        _objdelpos = FCtrl.FULL_RANGE_WIDTH / pdef.HOCScale
        _adjust = FCtrl.FULL_RANGE_WIDTH * np.cbrt(FCtrl.TGT_FORCE / pdef.MAX_HOC_FORCE)
        _objpos = (self.target + _adjust) / pdef.HOCScale
        return {"Position": -_objpos, "DelPosition": _objdelpos}


class StateMachine():
    def __init__(self, plutodev : QtPluto, data: PlutoForceControlData, instdisp):
        self._state = States.REST
        self._statetimer = 0
        self._data = data
        self._instruction = f""
        self._instdisp = instdisp
        self._pluto : QtPluto= plutodev
        self._statehandlers = {
            States.REST: self._handle_rest,
            States.WAIT_START: self._handle_wait_start,
            States.HOLDING: self._handle_holding,
            States.NOT_HOLDING: self._handle_holding,
            States.CRUSHING: self._handle_holding,
            States.RELAX: self._handle_relax,
            States.DONE: self._handle_done,
        }
        # Action handlers
        self._actionhandlers = {
            Actions.NO_CONTROL: self._act_no_control,
            Actions.SIM_OBJECT: self._act_sim_object,
            Actions.DISSOLVE_OBJECT: self._act_dissolve_object,
            Actions.DO_NOTHING: self._act_do_nothing, 
        }
        # State instructions
        self._stateinstructions = {
            States.WAIT_START: "Grab the object and hold to start trial",
            States.HOLDING: "Perfect grip",
            States.NOT_HOLDING: "More grip",
            States.CRUSHING: "Les grip",
            States.RELAX: "Relax.",
            States.DONE: "All done. Press the PLUTO button to exit.",
        }
        # Start a new trial.
        self._data.start_newtrial()

    @property
    def state(self):
        return self._state
    
    @property
    def in_a_trial_state(self):
        return self._state in [
            States.WAIT_START,
            States.HOLDING,
            States.NOT_HOLDING,
            States.CRUSHING 
        ]
    
    def reset_statemachine(self):
        self._state = States.REST
        self._statetimer = 0
        self._instruction = f""
        self._data.start_newtrial(reset=True)
    
    def run_statemachine(self, event, dt):
        """Execute the state machine depending on the given even that has occured.
        """
        _action = self._statehandlers[self._state](event, dt)
        self._actionhandlers[_action]()
        # Display instructions.
        self._display_instruction()

    def _handle_rest(self, event, dt):
        if not self._data.demomode and self._data.all_trials_done:
            self._data.terminate_rawlogging()
            self._data.terminate_summarylogging()
            if event == PlEvnts.RELEASED:
                self._state = States.DONE
                self._statetimer = None
            return Actions.NO_CONTROL
        if event == PlEvnts.RELEASED:
            if self.subj_outside_brick() and self.subj_is_holding():
                self._state = States.WAIT_START
                self._statetimer = FCtrl.HOLD_START_DURATION
                # Set the logging state.
                if not self._data.demomode: self._data.start_rawlogging()
                return Actions.SIM_OBJECT
        return Actions.NO_CONTROL

    def _handle_wait_start(self, event, dt):
        if event == PlEvnts.NEWDATA:
            if not self.is_object_held() or not self.subj_is_holding():
                self._statetimer = FCtrl.HOLD_START_DURATION
                return Actions.DO_NOTHING
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._state = States.HOLDING    
                self._statetimer = FCtrl.DURATION
                return Actions.SIM_OBJECT
        return Actions.DO_NOTHING
 
    def _handle_holding(self, event, dt):
        if event == PlEvnts.NEWDATA:
            self._statetimer -= dt
            if not self.is_object_held():
                self._state = (States.CRUSHING 
                               if self.is_object_crushed() 
                               else States.NOT_HOLDING)
            else:
                self._state = States.HOLDING
            if self._statetimer <= 0:
                self._state = States.RELAX
                self._statetimer = FCtrl.RELAX_DURATION
                return Actions.DO_NOTHING
        return Actions.DO_NOTHING

    def _handle_relax(self, event, dt):
        if event == PlEvnts.NEWDATA:
            self._statetimer -= dt
            if self._statetimer <= 0:
                self._data.trial_done()
                self._data.start_newtrial()
                self._state = States.REST
                self._statetimer = None
                return Actions.DISSOLVE_OBJECT
        return Actions.DISSOLVE_OBJECT

    def _handle_done(self, event, dt):
        return Actions.DO_NOTHING

    #
    # Action handlers
    #
    def _act_no_control(self):
        if self._pluto.controltype != pdef.ControlTypes["NONE"]:
            self._pluto.set_control_type("NONE")

    def _act_sim_object(self):
        if self._pluto.controltype != pdef.ControlTypes["OBJECTSIM"]:
            self._pluto.set_control_type("OBJECTSIM")
            self._pluto.set_object_param(self._data.object_params["DelPosition"],
                                            self._data.object_params["Position"])
            self._pluto.get_object_param()

    def _act_dissolve_object(self):
        if self._pluto.controlhold != pdef.ControlHoldTypes["DECAY"]:
            self._pluto.decay_control()

    def _act_do_nothing(self):
        pass

    def _display_instruction(self):
        self._instdisp.setText(self._stateinstructions[self._state] 
                               + f" [{self._statetimer:1.1f}s]" if self._statetimer else "")
        _trialstate = (self._state == States.HOLDING
                       or self._state == States.NOT_HOLDING
                       or self._state == States.CRUSHING)
        if self._state != States.REST and not _trialstate:
            self._instdisp.setPos(0, 20)
        elif _trialstate:
            self._instdisp.setPos(0, -5)
        else:
            self._instdisp.setPos(0, 20)
            if self._data.demomode:
                self._instdisp.setText(f"Press the PLUTO button to start demo trial.")
            elif self._data.all_trials_done:
                self._instdisp.setText(f"All trials done. Press the PLUTO button to quit.")
            else:
                self._instdisp.setText(f"PLUTO button to start trial {self._data.current_trial + 1} / {self._data.ntrials}.")

    #
    # Supporting functions
    #
    def subj_is_holding(self):
        """Check if the subject is holding the position.
        """
        _th = (ForceControl.VEL_HOC_THRESHOLD
               if self._data.mechanism == "HOC"
               else ForceControl.VEL_NOT_HOC_THRESHOLD)
        return bool(np.all(np.abs(self._data.trialdata['vel']) < _th))
    
    def subj_outside_brick(self):
        return self._pluto.hocdisp - self._data.target > 1.0
    
    def is_object_held(self):
        return np.abs(self._pluto.gripforce - FCtrl.TGT_FORCE) < FCtrl.TGT_FORCE_WIDTH
    
    def is_object_crushed(self):
        return self._pluto.gripforce - FCtrl.TGT_FORCE > FCtrl.TGT_FORCE_WIDTH
    
    def away_from_start(self):
        """Check if the subject has moved away from the start position.
        """
        if self._data.mechanism == "HOC":
            return np.abs(self._pluto.hocdisp - self._data.startpos) > pfadef.START_POS_HOC_THRESHOLD
        else:
            return np.abs(self._pluto.angle - self._data.startpos) > pfadef.START_POS_NOT_HOC_THRESHOLD
    
    def subj_in_the_stop_zone(self):
        """Check if the subject is in the stop zone.
        """
        if self._data.mechanism == "HOC":
            return (self._pluto.hocdisp - self._data.startpos) < pfadef.STOP_POS_HOC_THRESHOLD
        else:
            return np.abs(self._pluto.angle - self._data.startpos) < pfadef.STOP_POS_NOT_HOC_THRESHOLD


class PlutoForceControlWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the force control assessment task.
    """

    def __init__(self, parent=None, plutodev: QtPluto=None, assessinfo: dict=None, 
                 modal=False, dataviewer=False, onclosecb=None, heartbeat=False):
        """
        Constructor for the PlutoForceControlWindow class.
        """
        super(PlutoForceControlWindow, self).__init__(parent)
        self.ui = Ui_APRomAssessWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # Set the title of the window.
        self.setWindowTitle(
            " | ".join((
                "PLUTO Full Assessment",
                "Force Control",
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

        # APROM assessment data
        self.data: PlutoForceControlData = PlutoForceControlData(assessinfo=assessinfo)

        # Set control to NONE
        self._pluto.set_control_type("NONE")
        # Initialize graph for plotting
        self._fctrlassess_add_graph()

        # Visual feedback display timer
        self._visfeedtimer = QTimer()
        self._visfeedtimer.timeout.connect(self._update_current_position_cursor)
        self._visfeedtimer.start(pfadef.VISUAL_FEEDBACK_UPDATE_INTERVAL)
        

        # Initialize the state machine.
        self._smachine = StateMachine(self._pluto, self.data, self.ui.subjInst)
        
        # Attach callbacks
        self._attach_pluto_callbacks()

        # Attach control callbacks
        self.ui.cbTrialRun.clicked.connect(self._callback_trialrun_clicked)

        # Update UI.
        self.update_ui()

        # Set the callback when the window is closed.
        self.on_close_callback = onclosecb

        # Open the PLUTO data viewer window for sanity
        if dataviewer:
            # Open the device data viewer by default.
            self._open_devdata_viewer()

    @property
    def pluto(self):
        return self._pluto
    
    @property
    def statemachine(self):
        return self._smachine
    
    #
    # Update UI
    #
    def update_ui(self):
        # Trial run checkbox
        if self.ui.cbTrialRun.isEnabled():
            _cond1 = self.data.demomode is False
            _cond2 = (self.data.demomode is None
                      and self._smachine.state == States.WAIT_START)
            if _cond1 or _cond2:
                self.ui.cbTrialRun.setEnabled(False)
        
        # Update main text
        if self.pluto.angle is None: return
        _posstr = (f"[{self.pluto.hocdisp:5.2f}cm]" 
                   if self.data.mechanism == "HOC"
                   else f"[{self.pluto.angle:5.2f}deg]")
        self.ui.lblTitle.setText(f"PLUTO Force Control Assessment {_posstr}")

        # Update status message
        self.ui.lblStatus.setText(f"{self.pluto.error} | {self.pluto.controltype} | {self._smachine.state}")

        # Close if needed
        if self._smachine.state == States.DONE:
            self.close()
    
    def _update_current_position_cursor(self):
        if self.data.mechanism == "HOC":
            if self.pluto.hocdisp is None:
                return
            # Plot when there is data to be shown
            self.ui.currPosLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT]
            )
            self.ui.currPosLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT]
            )
            # Update object
            _objparams = self._compute_display_object_params(self.pluto.gripforce)
            self.ui._brick.setRect(_objparams["x"], _objparams["y"],
                                _objparams["width"], _objparams["height"])
            if self.pluto.gripforce < FCtrl.TGT_FORCE - FCtrl.TGT_FORCE_WIDTH:
                self.ui._brick.setBrush(QtGui.QBrush(FCtrl.FREE_COLOR))
            elif self.pluto.gripforce > FCtrl.TGT_FORCE + FCtrl.TGT_FORCE_WIDTH:
                self.ui._brick.setBrush(QtGui.QBrush(FCtrl.CRUSHED_COLOR))
            else:
                self.ui._brick.setBrush(QtGui.QBrush(FCtrl.HELD_COLOR))
        else:
            if self.pluto.angle is None:
                return
            self.ui.currPosLine1.setData(
                [self._dispsign * self.pluto.angle,
                 self._dispsign * self.pluto.angle],
                [ForceControl.CURSOR_LOWER_LIMIT,
                 ForceControl.CURSOR_UPPER_LIMIT]
            )
            self.ui.currPosLine2.setData(
                [self._dispsign * self.pluto.angle,
                 self._dispsign * self.pluto.angle],
                [ForceControl.CURSOR_LOWER_LIMIT,
                 ForceControl.CURSOR_UPPER_LIMIT]
            )

    def _draw_stop_zone_lines(self):
        _th = (pfadef.STOP_POS_HOC_THRESHOLD
               if self.data.mechanism == "HOC"
               else pfadef.STOP_POS_NOT_HOC_THRESHOLD)
        if self.data.mechanism == "HOC":
            self.ui.stopLine1.setData(
                [self.data.startpos + _th,
                 self.data.startpos + _th],
                [ForceControl.CURSOR_LOWER_LIMIT,
                 ForceControl.CURSOR_UPPER_LIMIT]
            )
            self.ui.stopLine2.setData(
                [-self.data.startpos - _th,
                 -self.data.startpos - _th],
                [ForceControl.CURSOR_LOWER_LIMIT,
                 ForceControl.CURSOR_UPPER_LIMIT]
            )
        else:
            self.ui.stopLine1.setData(
                [self._dispsign * (self.data.startpos - _th),
                 self._dispsign * (self.data.startpos - _th)],
                [ForceControl.CURSOR_LOWER_LIMIT,
                 ForceControl.CURSOR_UPPER_LIMIT]
            )
            self.ui.stopLine2.setData(
                [self._dispsign * (self.data.startpos + _th),
                 self._dispsign * (self.data.startpos + _th)],
                [ForceControl.CURSOR_LOWER_LIMIT,
                 ForceControl.CURSOR_UPPER_LIMIT]
            )
    
    def _update_arom_cursor_position(self):
        if len(self.data._trialrom) == 0: return
        if self.data.mechanism == "HOC":
            if len(self.data._trialrom) > 1:
                self.ui.romLine1.setData([-self.data._trialrom[-1], -self.data._trialrom[-1]],
                                         [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT])
                self.ui.romLine2.setData([self.data._trialrom[-1], self.data._trialrom[-1]],
                                         [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT])
                self.ui.romFill.setRect(-self.data._trialrom[-1], ForceControl.CURSOR_LOWER_LIMIT,
                                        2 * self.data._trialrom[-1], ForceControl.CURSOR_UPPER_LIMIT - ForceControl.CURSOR_LOWER_LIMIT)
            else:
                self.ui.romLine1.setData([0, 0], [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT])
                self.ui.romLine2.setData([0, 0], [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT])
                self.ui.romFill.setRect(0, ForceControl.CURSOR_LOWER_LIMIT, 0, ForceControl.CURSOR_UPPER_LIMIT - ForceControl.CURSOR_LOWER_LIMIT)
        else:
            _romdisp = list(map(lambda x: self._dispsign * x, self.data._trialrom))
            _romdisp.sort()
            self.ui.romLine1.setData(
                [_romdisp[0], _romdisp[0]],
                [ForceControl.CURSOR_LOWER_LIMIT,
                 ForceControl.CURSOR_UPPER_LIMIT]
            )
            self.ui.romLine2.setData(
                [_romdisp[-1], _romdisp[-1]],
                [ForceControl.CURSOR_LOWER_LIMIT,
                 ForceControl.CURSOR_UPPER_LIMIT]
            )
            # Fill between the two AROM lines
            self.ui.romFill.setRect(
                _romdisp[0], ForceControl.CURSOR_LOWER_LIMIT,
                _romdisp[-1] - _romdisp[0],
                ForceControl.CURSOR_UPPER_LIMIT - ForceControl.CURSOR_LOWER_LIMIT
            )
    
    def _highlight_start_zone(self):
        if len(self.data._trialrom) == 0: return
        # Fill the start zone
        if self._smachine.state == States.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE:
            if self.data.mechanism == "HOC":
                self.ui.strtZoneFill.setRect(
                    -self.data.startpos - pfadef.STOP_POS_HOC_THRESHOLD,
                    ForceControl.CURSOR_LOWER_LIMIT,
                    2 * (self.data.startpos + pfadef.STOP_POS_HOC_THRESHOLD),
                    ForceControl.CURSOR_UPPER_LIMIT - ForceControl.CURSOR_LOWER_LIMIT
                )
            else:
                self.ui.strtZoneFill.setRect(
                    self._dispsign * self.data.startpos - pfadef.STOP_POS_NOT_HOC_THRESHOLD,
                    ForceControl.CURSOR_LOWER_LIMIT,
                    2 * pfadef.STOP_POS_NOT_HOC_THRESHOLD,
                    ForceControl.CURSOR_UPPER_LIMIT - ForceControl.CURSOR_LOWER_LIMIT
                )
        else:
            self.ui.strtZoneFill.setRect(0, ForceControl.CURSOR_LOWER_LIMIT,
                                         0, ForceControl.CURSOR_UPPER_LIMIT - ForceControl.CURSOR_LOWER_LIMIT)
    
    def _reset_display(self):
        # Reset ROM display
        # self.ui.romLine1.setData(
        #     [0, 0],
        #     [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT]
        # )
        # self.ui.romLine2.setData(
        #     [0, 0],
        #     [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT]
        # )
        # # Fill between the two AROM lines
        # self.ui.romFill.setRect(0, ForceControl.CURSOR_LOWER_LIMIT,
        #                         0, ForceControl.CURSOR_UPPER_LIMIT - ForceControl.CURSOR_LOWER_LIMIT)
        # # Reset stop zone.
        # self.ui.stopLine1.setData(
        #     [0, 0],
        #     [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT]
        # )
        # self.ui.stopLine2.setData(
        #     [0, 0],
        #     [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT]
        # )
        # self.ui.strtZoneFill.setRect(0, ForceControl.CURSOR_LOWER_LIMIT,
        #                              0, ForceControl.CURSOR_UPPER_LIMIT - ForceControl.CURSOR_LOWER_LIMIT)
        pass

    #
    # Graph plot initialization
    #
    def _fctrlassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self.ui.hocGraph.setLayout(_templayout)
        if self.data.mechanism == "HOC":
            _pgobj.setXRange(-self.data.arom[1], self.data.arom[1])
        else:
            _pgobj.setXRange(pdef.PlutoAngleRanges[self.data.mechanism][0],
                             pdef.PlutoAngleRanges[self.data.mechanism][1])
        _pgobj.setYRange(-20, 30)
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Current position lines
        self.ui.currPosLine1 = pg.PlotDataItem(
            [0, 0],
            [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        self.ui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [ForceControl.CURSOR_LOWER_LIMIT, ForceControl.CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        _pgobj.addItem(self.ui.currPosLine1)
        _pgobj.addItem(self.ui.currPosLine2)

        self.ui._brick = QGraphicsRectItem()
        _objparams = self._compute_display_object_params(self.pluto.gripforce)
        self.ui._brick.setRect(_objparams["x"], _objparams["y"],
                               _objparams["width"], _objparams["height"])
        self.ui._brick.setBrush(QtGui.QBrush(FCtrl.FREE_COLOR))
        self.ui._brick.setPen(pg.mkPen(None))
        _pgobj.addItem(self.ui._brick)

        # Instruction text
        self.ui.subjInst = pg.TextItem(text='', color='w', anchor=(0.5, 0.5))
        self.ui.subjInst.setPos(0, 20)
        # Set font and size
        self.ui.subjInst.setFont(QtGui.QFont("Cascadia Mono Light", 14))
        _pgobj.addItem(self.ui.subjInst)
    
    def _compute_display_object_params(self, force):
        # Object width
        _tgtmid = np.cbrt(FCtrl.TGT_FORCE / pdef.MAX_HOC_FORCE)
        if force is None or force < FCtrl.TGT_FORCE - FCtrl.TGT_FORCE_WIDTH:
            _tgtlow = np.cbrt((FCtrl.TGT_FORCE - FCtrl.TGT_FORCE_WIDTH) / pdef.MAX_HOC_FORCE)
        else:
            _tgtlow = np.cbrt(force / pdef.MAX_HOC_FORCE)
        _objwidth = float(self.data.target + (_tgtmid - _tgtlow) * FCtrl.FULL_RANGE_WIDTH)
        # Object height
        _objheight = float(10 * self.data.target  / _objwidth)
        return {"width": 2 * _objwidth, "height": 2 * _objheight,
                "x": -_objwidth, "y": -_objheight-5}

    #
    # Device PlutoForceControlData Viewer Functions 
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
        # Update trial data.
        self.data.add_newdata(
            dt=self.pluto.delt(),
            pos=self.pluto.hocdisp if self.data.mechanism == "HOC" else self.pluto.angle
        )
        # Run the statemachine
        _action = self._smachine.run_statemachine(
            PlEvnts.NEWDATA,
            dt=self.pluto.delt()
        )
        # Update the GUI only at 1/10 the data rate
        if np.random.rand() < 0.1:
            self.update_ui()
        #
        # Log data
        if self.data.logstate == LogState.LOG_DATA:        
            self.data.rawfilewriter.write_row([
                self.pluto.systime,
                self.pluto.currt,
                self.pluto.packetnumber,
                self.pluto.status,
                self.pluto.controltype,
                self.pluto.error,
                self.pluto.limb,
                self.pluto.mechanism,
                self.pluto.angle,
                self.pluto.hocdisp,
                self.pluto.torque,
                self.pluto.gripforce,
                self.pluto.control,
                self.pluto.controlhold,
                self.pluto.button,
                self.pluto.objectPosition,
                self.pluto.objectDelPosition,
                self.data.currtrial,
                f"{self._smachine.state.name}"
            ])

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        _action = self._smachine.run_statemachine(
            PlEvnts.RELEASED,
            dt=self.pluto.delt()
        )
        self.update_ui()

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
    
    def closeEvent(self, event):
        # Get comment from the experimenter.
        data = {"done": self.data.all_trials_done}
        self.pluto.set_control_type("NONE")
        if self.data.all_trials_done:
            _comment = CommentDialog(label="Assisted PROM completed. Add optional comment.",
                                     commentrequired=False)
            data["status"] = pfadef.AssessStatus.COMPLETE.value
        else:
            _comment = CommentDialog(label="Assisted PROM incomplete. Why?",
                                     commentrequired=True)
            data["status"] = pfadef.AssessStatus.SKIPPED.value
        if (_comment.exec_() == QtWidgets.QDialog.Accepted):
            data["taskcomment"] = _comment.getText()
        if self.on_close_callback:
            self.on_close_callback(data=data)
        # Detach PLUTO callbacks.
        self._detach_pluto_callbacks()
        try:
            self._devdatawnd.close()
        except:
            pass
        return super().closeEvent(event)


if __name__ == '__main__':
    import qtjedi
    qtjedi._OUTDEBUG = False
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM12")
    pcalib = PlutoForceControlWindow(
        plutodev=plutodev, 
        assessinfo={
            "subjid": "",
            "type": "Stroke",
            "limb": "Left",
            "mechanism": "HOC",
            "session": "testing",
            "ntrials": 3,
            "rawfile": "rawfiletest.csv",
            "summaryfile": "summaryfiletest.csv",
            "arom": [0, 6],
        },
        dataviewer=True,
        onclosecb=lambda data: print(f"ROM set: {data}"),
        heartbeat=True
    )
    pcalib.show()
    sys.exit(app.exec_())
