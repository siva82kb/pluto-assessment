"""
Module for handling the operation of the position hold assessment 
with PLUTO.

Author: Sivakumar Balasubramanian
Date: 09 June 2025
Email: siva82kb@gmail.com
"""


import sys
import numpy as np
import random

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,
    QtGui)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QTimer, QPointF
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtCore import pyqtSignal
import pyqtgraph as pg
from enum import Enum, auto

import plutodefs as pdef
import plutofullassessdef as pfadef
from plutofullassessdef import PositionHold
from plutoapromwindow import RawDataLoggingState
from ui_plutoposholdassess import Ui_PosHoldAssessWindow
from myqt import CommentDialog
from myqt import create_sector

from misc import CSVBufferWriter 


class States(Enum):
    REST = auto()
    GOTO_TGT = auto()
    HOLD_TGT = auto()
    DONE = auto()


class PositionHoldData(object):
    def __init__(self, assessinfo: dict):
        self._assessinfo = assessinfo
        self._demomode = None
        # Trial variables
        self._currtrial = 0
        self._targets = []
        self._generate_targets()
        self._trialdata = {"dt": [], "pos": [], "vel": []}
        self._currtrial = -1
        self._currtarget = None
        # Logging variables
        self._logstate: RawDataLoggingState = RawDataLoggingState.WAIT_FOR_LOG
        self._rawfilewriter: CSVBufferWriter = CSVBufferWriter(
            self.rawfile, 
            header=PositionHold.RAW_HEADER
        )
    
    @property
    def type(self):
        return self._assessinfo['type']

    @property
    def limb(self):
        return self._assessinfo['limb']

    @property
    def mechanism(self):
        return self._assessinfo['mechanism']
    
    @property
    def session(self):
        return self._assessinfo['session']

    @property
    def ntrials(self):
        return self._assessinfo['ntrials']
    
    @property
    def targets(self):
        return self._targets

    @property
    def current_target(self):
        return self._currtarget
    
    @property
    def current_trial(self):
        return self._currtrial
    
    @property
    def rawfile(self):
        return self._assessinfo['rawfile']
    
    @property
    def arom(self):
        return self._assessinfo["arom"]
    
    @property
    def aromrange(self):
        return self.arom[1] - self.arom[0]

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
        return self._currtrial == len(self.targets) - 1
    
    @property
    def rawfilewriter(self):
        return self._rawfilewriter
    
    def start_newtrial(self, reset: bool = False):
        """Start a new trial.
        """
        if not self.all_trials_done:
            self._trialdata = {"dt": [], "pos": [], "vel": []}
            self._trialrom = []
            self._startpos = None
            self._currtrial = 0 if reset else self._currtrial + 1
            self._currtarget = self._targets[self._currtrial]

    def _generate_targets(self):
        # Target positions.
        _temp1 = [self.aromrange * _tgt + self.arom[0]
                  for _tgt in PositionHold.TGT_POSITIONS]
        random.shuffle(_temp1)
        _temp2 = [self.aromrange * _tgt + self.arom[0]
                  for _n in range(self.ntrials-1) 
                  for _tgt in PositionHold.TGT_POSITIONS]
        random.shuffle(_temp2)
        self._targets = _temp1 + _temp2
        print(f"Generated targets: {self._targets}")

    def add_newdata(self, dt, pos):
        """Add new data to the trial data.
        """
        self._trialdata['dt'].append(dt)
        self._trialdata['pos'].append(pos)
        self._trialdata['vel'].append((pos - self._trialdata['pos'][-2]) / dt
                                      if len(self._trialdata['pos']) > 1
                                      else 0)
        if len(self._trialdata['dt']) > PositionHold.POS_VEL_WINDOW_LENGHT:
            self._trialdata['dt'].pop(0)
            self._trialdata['pos'].pop(0)
            self._trialdata['vel'].pop(0)
    
    def add_new_trialrom_data(self) -> bool:
        """Add new value to trial ROM.
        """
        _pos = float(np.mean(self._trialdata['pos']))
        if self.arom is None:
            self._trialrom.append(_pos)
            self._trialrom.sort()
            return True
        # Check if the rom value is outside AROM
        if _pos <= self.arom[0] or _pos >= self.arom[1]:
            self._trialrom.append(_pos)
            self._trialrom.sort()
            return True
        return False

    def start_rawlogging(self):
        self._logstate = RawDataLoggingState.LOG_DATA
    
    def terminate_rawlogging(self):
        self._logstate = RawDataLoggingState.LOGGING_DONE
        self._rawfilewriter.close()
        self._rawfilewriter = None
    
    def terminate_summarylogging(self):
        self._summaryfilewriter.close()
        self._summaryfilewriter = None


class PlutoAPRomAssessmentStateMachine():
    def __init__(self, plutodev, data: PositionHoldData, instdisp):
        self._state = States.REST
        self._statetimer = 0
        self._holdreachtimer = 0
        self._data = data
        self._instdisp = instdisp
        self._pluto = plutodev
        self._stateactions = {
            States.REST: self._handle_rest,
            States.GOTO_TGT: self._handle_goto_tgt,
            States.HOLD_TGT: self._handle_hold_tgt,
            States.DONE: self._handle_done
        }
        
        # State instructions
        self._stateinstructions = {
            States.REST: "",
            States.GOTO_TGT: "Go to target.",
            States.HOLD_TGT: "Hold at target.",
            States.DONE: "All done. Press Pluto Button to exit."
        }
        # Start a new trial.
        self._data.start_newtrial()

    @property
    def state(self):
        return self._state
    
    @property
    def in_a_trial_state(self):
        return self._state != States.REST
    
    def reset_statemachine(self):
        self._state = States.REST
        self._statetimer = 0
        self._instruction = f""
        self._data.start_newtrial(reset=True)
    
    def run_statemachine(self, event, dt):
        """Execute the state machine depending on the given even that has occured.
        Returns if the UI needs an immediate update.
        """
        retval = self._stateactions[self._state](event, dt)
        self._display_instruction()
        return retval

    def _handle_rest(self, event, dt):
        """
        """
        # Check if all trials are done.
        if not self._data.demomode and self._data.all_trials_done:
            # Set the logging state.
            if self._data.rawfilewriter is not None: 
                self._data.terminate_rawlogging()
            if event == pdef.PlutoEvents.RELEASED:
                self._state = States.DONE
                self._statetimer = 0
            return
        # Wait for start.
        if event == pdef.PlutoEvents.RELEASED:
            self._state = States.GOTO_TGT
            self._statetimer = PositionHold.TGT_HOLD_DURATION
            # Set the logging state.
            if not self._data.demomode: self._data.start_rawlogging()

    def _handle_goto_tgt(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            # Check if within tartget.
            if self.subj_in_target():
                self._statetimer -= dt
                self._state = States.HOLD_TGT
            if self._statetimer < 0:
                # Failed trial.
                self._state = States.REST
                # Set the ROM for the current trial.
                if not self._data.demomode:
                    self._data.start_newtrial()

    def _handle_hold_tgt(self, event, dt):
        """
        """
        if event == pdef.PlutoEvents.NEWDATA:
            # Check if within tartget.
            if not self.subj_in_target():
                self._state = States.GOTO_TGT
            self._statetimer -= dt
            if self._statetimer < 0:
                # Failed trial.
                self._state = States.REST
                 # Set the ROM for the current trial.
                if not self._data.demomode:
                    self._data.start_newtrial()

    
    def _handle_done(self, event, dt):
        pass
        
    def _display_instruction(self):
        if self._state != States.REST:
            self._instdisp.setText(
                self._stateinstructions[self._state] 
                + (f" [{np.max([0.0, self._statetimer]):1.1f}s]"
                   if self._statetimer is not None else "")
            )
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
    def subj_in_target(self):
        """Check if the subject is in target.
        """
        return np.abs(self._pluto.angle - self._data.current_target) < 0.5 * PositionHold.TGT_WIDTH_DEG
    
    def subj_in_target2(self):
        """Check if the subject is in target2.
        """
        return np.abs(self._pluto.angle - self._data.target2) < 0.5 * PositionHold.TGT_WIDTH * self._data.aromrange
    
    def subj_is_holding(self):
        """Check if the subject is holding the position.
        """
        _th = (PositionHold.VEL_HOC_THRESHOLD
               if self._data.mechanism == "HOC"
               else PositionHold.VEL_NOT_HOC_THRESHOLD)
        return bool(np.all(np.abs(self._data.trialdata['vel']) < _th))
    
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


class PlutoPositionHoldAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO ROM assessment window.
    """

    def __init__(self, parent=None, plutodev: QtPluto=None, assessinfo: dict=None, modal=False, onclosecb=None):
        """
        Constructor for the PlutoPositionHoldAssessWindow class.
        """
        super(PlutoPositionHoldAssessWindow, self).__init__(parent)
        self.ui = Ui_PosHoldAssessWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # Set the title of the window.
        self.setWindowTitle(
            " | ".join((
                "PLUTO Full Assessment",
                "Discrete Reaching",
                f"{assessinfo['subjid'] if 'subjid' in assessinfo else ''}",
                f"{assessinfo['type'] if 'type' in assessinfo else ''}",
                f"{assessinfo['limb'] if 'limb' in assessinfo else ''}",
                f"{assessinfo['mechanism'] if 'mechanism' in assessinfo else ''}",
                f"{assessinfo['session'] if 'session' in assessinfo else ''}",
            ))
        )
        
        # PLUTO device
        self._pluto = plutodev

        # APROM assessment data
        self.data: PositionHoldData = PositionHoldData(assessinfo=assessinfo)

        # Set control to NONE
        self._pluto.set_control_type("NONE")
        
        # Visual feedback display timer
        self._visfeedtimer = QTimer()
        self._visfeedtimer.timeout.connect(self._update_visual_feedabck)
        self._visfeedtimer.start(pfadef.VISUAL_FEEDBACK_UPDATE_INTERVAL)

        # Initialize graph for plotting
        self._romassess_add_graph()

        # Initialize the state machine.
        self._smachine = PlutoAPRomAssessmentStateMachine(
            self._pluto, 
            self.data, 
            self.ui.subjInst
        )

        # Attach callbacks
        self._attach_pluto_callbacks()

        # Attach control callbacks
        self.ui.cbTrialRun.clicked.connect(self._callback_trialrun_clicked)

        # Update UI.
        self.update_ui()

        # Set the callback when the window is closed.
        self.on_close_callback = onclosecb

    @property
    def pluto(self):
        return self._pluto
    
    @property
    def statemachine(self):
        return self._smachine
    
    @property
    def current_polar_pos(self):
        if self._pluto.angle is None:
            return [0, 0]
        return [50 * np.cos(np.deg2rad(self._pluto.angle + 90)),
                50 * np.sin(np.deg2rad(self._pluto.angle + 90))]
    #
    # Update UI
    #
    def update_ui(self):
        # Trial run checkbox
        if self.ui.cbTrialRun.isEnabled():
            _cond1 = self.data.demomode is False
            _cond2 = (self.data.demomode is None
                      and self._smachine.state == States.GOTO_TGT)
            if _cond1 or _cond2:
                self.ui.cbTrialRun.setEnabled(False)

        # Update main text
        if self.pluto.angle is None: return
        _posstr = (f"[{self.pluto.hocdisp:5.2f}cm]" 
                   if self.data.mechanism == "HOC"
                   else f"[{self.pluto.angle:5.2f}deg]")
        self.ui.lblTitle.setText(f"Dsicrete Reach Assessment {_posstr}")

        # Update status message
        self.ui.lblStatus.setText(f"{self._smachine.state}")

        # Close if needed
        if self._smachine.state == States.DONE:
            self.close()
        
    def _update_visual_feedabck(self):
        self._update_current_position_cursor()
        self._updat_targets_display()

    def _update_current_position_cursor(self):
        if self.data.mechanism == "HOC":
            if self.pluto.hocdisp is None:
                return
            # Plot when there is data to be shown
            self.ui.currPosLine.setData(
                [0, self.current_polar_pos[0]],
                [0, self.current_polar_pos[1]]
            )
        else:
            if self.pluto.angle is None:
                return
            self.ui.currPosLine.setData(
                [0, self.current_polar_pos[0]],
                [0, self.current_polar_pos[1]]
            )
    
    def _updat_targets_display(self):
        # Display depending on the state.
        if self._smachine.state == States.REST:
            # Hide both targets.
            for _t in self.ui.tgt.values():
                _t.setBrush(PositionHold.HIDE_COLOR)
        elif self._smachine.state == States.GOTO_TGT:
            self.ui.tgt[self.data.current_target].setBrush(PositionHold.TARGET_DISPLAY_COLOR)
        elif self._smachine.state == States.HOLD_TGT:
            self.ui.tgt[self.data.current_target].setBrush(PositionHold.TARGET_REACHED_COLOR)

    #
    # Graph plot initialization
    #
    def _romassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        # Angle display sign for the limb.
        self._dispsign = 1.0 if self.data.limb.upper() == "RIGHT" else -1.0
        
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self.ui.hocGraph.setLayout(_templayout)
        _aromdisp = list(map(lambda x: self._dispsign * x, self.data.arom))
        _aromdisp.sort()
        _pgobj.setXRange(-50, 50)
        _pgobj.setYRange(0, 75)
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Generate the target sectors
        self.ui.tgt = {
            _t:create_sector(center=QPointF(0, 0),
                             radius=50,
                             start_angle_deg=90 + _t - 0.5 * PositionHold.TGT_WIDTH_DEG,
                             span_angle_deg=PositionHold.TGT_WIDTH_DEG,
                             color=PositionHold.TARGET_DISPLAY_COLOR)
            for _t in list(set(self.data.targets))
        }
        for k, v in self.ui.tgt.items():
            _pgobj.addItem(v)

        # Draw a semicircular arc
        _ang = np.linspace(0, np.pi, 100)
        self.ui.arc = pg.PlotCurveItem(
            x=50 * np.cos(_ang),
            y=50 * np.sin(_ang),
            pen=pg.mkPen(color=(255, 255, 255, 100), width=1)
        )
        _pgobj.addItem(self.ui.arc)
        
        # Current position lines
        self.ui.currPosLine = pg.PlotDataItem(
            [0, self.current_polar_pos[0]],
            [0, self.current_polar_pos[1]],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        _pgobj.addItem(self.ui.currPosLine)
       
        # Instruction text
        self.ui.subjInst = pg.TextItem(text='', color='w', anchor=(0.5, 0.5))
        self.ui.subjInst.setPos(0, 70)  # Set position (x, y)
        self.ui.subjInst.setFont(QtGui.QFont("Cascadia Mono Light", 10))
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
            pos=self.pluto.hocdisp if self.data.mechanism == "HOC" else self.pluto.angle
        )
        # Run the statemachine
        _uiupdate = self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA,
            dt=self.pluto.delt()
        )
        # Update the GUI only at 1/10 the data rate
        if _uiupdate or np.random.rand() < 0.1:
            self.update_ui()
        #
        # Log data
        if self.data.logstate == RawDataLoggingState.LOG_DATA:        
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
                self.pluto.button,
                self.data.current_trial,
                f"{self._smachine.state.name}"
            ])

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        apromset = self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED,
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
        if self.data.all_trials_done:
            _comment = CommentDialog(label="Position Hold completed. Add optional comment.",
                                     commentrequired=False)
            data["status"] = pfadef.AssessStatus.COMPLETE.value
        else:
            _comment = CommentDialog(label="Position Hold incomplete. Why?",
                                     commentrequired=True)
            data["status"] = pfadef.AssessStatus.SKIPPED.value
        if (_comment.exec_() == QtWidgets.QDialog.Accepted):
            data["taskcomment"] = _comment.getText()
        if self.on_close_callback:
            self.on_close_callback(data=data)
        # Detach PLUTO callbacks.
        self._detach_pluto_callbacks()
        return super().closeEvent(event)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM12")
    pcalib = PlutoPositionHoldAssessWindow(
        plutodev=plutodev, 
        assessinfo={
            "subjid": "1234",
            "type": "Stroke",
            "limb": "Left",
            "mechanism": "WFE",
            "session": "testing",
            "ntrials": 3,
            "rawfile": "rawfiletest.csv",
            "arom": [-20, 30],
        },
        onclosecb=lambda data: print(f"ROM set: {data}"),
    )
    pcalib.show()
    sys.exit(app.exec_())
