"""
Module for handling the operation of the PLUTO active, passive, and assisted 
passive range of motion assesmsent window.

Author: Sivakumar Balasubramanian
Date: 22 May 2025
Email: siva82kb@gmail.com
"""


import sys
import numpy as np

from qtpluto import QtPluto

from PyQt5 import (
    QtCore,
    QtWidgets,)
from PyQt5.QtCore import pyqtSignal
import pyqtgraph as pg
from enum import Enum

import plutodefs as pdef
from ui_plutoapromassess import Ui_APRomAssessWindow


#
# APROM Assessment Constants
#
POS_VEL_WINDOW_LENGHT = 50
START_POS_HOC_THRESHOLD = 0.5       # cm
START_POS_NOT_HOC_THRESHOLD = 5     # cm
VEL_HOC_THRESHOLD = 1               # cm/sec
VEL_NOT_HOC_THRESHOLD = 5           # deg/sec

class PlutoAPRomAssessStates(Enum):
    FREE_RUNNING = 0
    TRIAL_ACTIVE_WAIT_TO_MOVE = 1
    TRIAL_ACTIVE_MOVING = 2
    TRIAL_ACTIVE_HOLDING = 3
    TRIAL_ACTIVE_NEW_ROM_SET = 4
    ROM_DONE = 5


class PlutoAPRomData(object):
    def __init__(self, mechname, romtype, ntrials):
        self._mechname = mechname
        self._romtype = romtype
        self._ntrials = ntrials
        self._demodone = None
        self._trialsdone = 0
        self._startpos = None
        self._trialrom = []
        self._trialdata = {"dt": [], "pos": [], "vel": []}
        self._trialsdone = 0
        self._rom = [[] for _ in range(ntrials)]

    @property
    def mechanism(self):
        return self._mechname

    @property
    def romtype(self):
        return self._romtype

    @property
    def ntrials(self):
        return self._ntrials

    @property
    def trialsdone(self):
        return self._trialsdone
    
    @property
    def rom(self):
        return self._rom
    
    @property
    def startpos(self):
        return self._startpos
    
    @property
    def trialdata(self):
        return self._trialdata
    
    @property
    def demomode(self):
        return self._demodone
    
    @demomode.setter
    def demomode(self, value):
        self._demodone = value
    
    @property
    def all_trials_done(self):
        """Check if all trials are done.
        """
        return self._trialsdone >= self._ntrials
    
    def start_newtrial(self):
        """Start a new trial.
        """
        if self._trialsdone < self._ntrials:
            self._trialdata = {"dt": [], "pos": [], "vel": []}
            self._trialsdone += 1

    def add_newdata(self, dt, pos):
        """Add new data to the trial data.
        """
        self._trialdata['dt'].append(dt)
        self._trialdata['pos'].append(pos)
        if len(self._trialdata['pos']) > 1:
            self._trialdata['vel'].append((pos - self._trialdata['pos'][-2]) / dt)
        else:
            self._trialdata['vel'].append(0)
        if len(self._trialdata['dt']) > POS_VEL_WINDOW_LENGHT:
            self._trialdata['dt'].pop(0)
            self._trialdata['pos'].pop(0)
            self._trialdata['vel'].pop(0)
    
    def set_rom(self, romval, trial):
        """Set the ROM value for the given trial.
        """
        if trial < self._ntrials:
            # Check of the values make sense.
            if romval[0] < romval[1]:
                self._rom[trial] = romval
            else:
                raise ValueError("First value should be less than second value.")
        else:
            raise ValueError("Trial number out of range.")
        
    def set_startpos(self):
        """Sets the start position as the average of trial data.
        """
        self._startpos = np.mean(self._trialdata['pos'])


class PlutoAPRomAssessmentStateMachine():
    def __init__(self, plutodev, data: PlutoAPRomData, logconsole):
        self._state = PlutoAPRomAssessStates.FREE_RUNNING
        self._data = data
        self._instruction = f"Assessing {self._data.romtype} ROM. Hold still and press button to start."
        self._logconsole = logconsole
        self._pluto = plutodev
        self._stateactions = {
            PlutoAPRomAssessStates.FREE_RUNNING: self._free_running,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE: self._trial_active_wait_to_move,
            PlutoAPRomAssessStates.ROM_DONE: self._rom_done
        }

    @property
    def state(self):
        return self._state
    
    @property
    def in_a_trial_state(self):
        return self._state in [
            PlutoAPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_MOVING,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_HOLDING,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_NEW_ROM_SET
        ]

    @property
    def instruction(self):
        return self._instruction

    def run_statemachine(self, event):
        """Execute the state machine depending on the given even that has occured.
        """
        return self._stateactions[self._state](event)

    def _free_running(self, event):
        # Wait for start.
        if event == pdef.PlutoEvents.RELEASED:
            # Check assessment is completed.
            if self._data.all_trials_done:
                self._instruction = f"{self._data.romtype}  Assessment Done.\nPress the PLUTO Button to exit."
                self._state = PlutoAPRomAssessStates.ROM_DONE
            else:
                # Make sure the joint is in rest before we can swtich.
                if self._subj_is_holding():
                    self._data.set_startpos()
                    self._trialrom = [] if self._data.mechanism != "HOC" else [0,]
                    self._state = PlutoAPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE
        self._logconsole.setText(self._instruction)
    
    def _trial_active_wait_to_move(self, event):
        self._instruction = f"Assessing {self._data.romtype}. Move an hold position.\nPress the PLUTO Button to end trial."
        # Check if new data.
        if event == pdef.PlutoEvents.NEWDATA:
            # Wait for the subject to away from the start position.
            if self._subj_is_holding() is False and self._awat_from_start():
                self._state = PlutoAPRomAssessStates.TRIAL_ACTIVE_MOVING
            else:
                self._instruction = f"{self._data.romtype} Move and hold to record ROM position."
        self._logconsole.setText(self._instruction)
 
    def _trial_active_max(self, event):
        if event == pdef.PlutoEvents.RELEASED:
            self._trialsdone += 1
            self._state = PlutoAPRomAssessStates.FREE_RUNNING
        # # Check if the button release event has happened.
        # if event == pdef.PlutoEvents.RELEASED:
        #     self._arom = abs(self._pluto.hocdisp)
        #     # Update PROM if needed
        #     self._prom = self._arom if self._arom > self._prom else self._prom
        #     # Update the instruction
        #     self._instruction = "Select AROM or PROM to assess."
        #     self._state = PlutoAPRomAssessStates.FREE_RUNNING
        #     return "aromset"
 
    def _prom_assess(self, event):
        # Check if the button release event has happened.
        if event == pdef.PlutoEvents.RELEASED:
            if abs(self._pluto.hocdisp) >= self._arom:
                self._prom = abs(self._pluto.hocdisp)
                # Update the instruction
                self._instruction = "Select AROM or PROM to assess."
                self._state = PlutoAPRomAssessStates.FREE_RUNNING
                return "promset"
            else:
                # Update the instruction
                self._instruction = "Error! PROM cannot be less than AROM.\nAssessing PROM. Press the PLUTO Button when done."
                pass
    
    def _rom_done(self, event):
        pass

    #
    # Supporting functions
    #
    def _subj_is_holding(self):
        """Check if the subject is holding the position.
        """
        _th = (VEL_HOC_THRESHOLD
               if self._data.mechanism == "HOC"
               else VEL_NOT_HOC_THRESHOLD)
        return np.all(np.abs(self._data.trialdata['vel']) < _th)
    
    def _awat_from_start(self):
        """Check if the subject has moved away from the start position.
        """
        _th = (START_POS_HOC_THRESHOLD 
               if self._data.mechanism 
               else START_POS_NOT_HOC_THRESHOLD)
        return np.abs(self._data.startpos - self._pluto.angle) > _th


class PlutoAPRomAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO ROM assessment window.
    """
    aromset = pyqtSignal()
    promset = pyqtSignal()

    def __init__(self, parent=None, plutodev: QtPluto=None, mechanism: str=None, 
                 romtype: str="Active", ntrials: int=1, modal=False):
        """
        Constructor for the PlutoAPRomAssessWindow class.
        """
        super(PlutoAPRomAssessWindow, self).__init__(parent)
        self.ui = Ui_APRomAssessWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # PLUTO device
        self._pluto = plutodev
        self.data = PlutoAPRomData(mechanism, romtype, ntrials)

        # Set control to NONE
        self._pluto.set_control_type("NONE")

        # Initialize the state machine.
        self._smachine = PlutoAPRomAssessmentStateMachine(self._pluto, self.data, self.ui.textInstruction)

        # Initialize graph for plotting
        self._romassess_add_graph()

        # Attach callbacks
        self.pluto.newdata.connect(self._callback_pluto_newdata)
        self.pluto.btnreleased.connect(self._callback_pluto_btn_released)

        # Attach control callbacks
        self.ui.cbTrialRun.clicked.connect(self._callback_trialrun_clicked)

        # Update UI.
        self.update_ui()

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
        return self._smachine.arom
    
    @property
    def prom(self):
        return self._smachine.prom
    
    #
    # Update UI
    #
    def update_ui(self):
        # Trial run checkbox
        self.ui.cbTrialRun.setEnabled(self.data.demomode is not True)
        # Update the graph display
        # Current position
        if self._smachine.state == PlutoAPRomAssessStates.FREE_RUNNING:
            self._update_freerun_cursor_position()
        elif self._smachine.in_a_trial_state:
            self._update_arom_cursor_position()
        # elif self._smachine.state == PlutoAPRomAssessStates.PROM_ASSESS:
        #     self.ui.currPosLine1.setData([0, 0], [-30, 30])
        #     self.ui.currPosLine2.setData([0, 0], [-30, 30])
        #     # PROM position
        #     self.ui.promLine1.setData(
        #         [self.pluto.hocdisp, self.pluto.hocdisp],
        #         [-30, 30]
        #     )
        #     self.ui.promLine2.setData(
        #         [-self.pluto.hocdisp, -self.pluto.hocdisp],
        #         [-30, 30]
        #     )

        # Update main text
        if self.pluto.angle is None: return
        _posstr = (f"[{self.pluto.hocdisp:5.2f}cm]" 
                   if self.data.mechanism == "HOC"
                   else f"[{self.pluto.angle:5.2f}deg]")
        self.ui.lblTitle.setText(f"PLUTO {self.data.romtype} ROM Assessment {_posstr}")

        # Update status message
        self.ui.lblStatus.setText(f"{self._smachine.state}")
        # self.ui.textInstruction.setText(self._smachine.instruction)

        # Update buttons
        # self.ui.pbArom.setText(f"Assess AROM [{self.arom:5.2f}cm]")
        # self.ui.pbProm.setText(f"Assess PROM [{self.prom:5.2f}cm]")
        # self.ui.pbArom.setEnabled(
        #     self._smachine.state == PlutoAPRomAssessStates.FREE_RUNNING
        # )
        # self.ui.pbProm.setEnabled(
        #     self._smachine.state == PlutoAPRomAssessStates.FREE_RUNNING
        # )

        # Close if needed
        if self._smachine.state == PlutoAPRomAssessStates.ROM_DONE:
            self.close()
    
    def _update_freerun_cursor_position(self):
        if self.data.mechanism == "HOC":
            if self.pluto.hocdisp is None:
                return
            # Plot when there is data to be shown
            self.ui.currPosLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self.ui.currPosLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )
        else:
            if self.pluto.angle is None:
                return
            self.ui.currPosLine1.setData([self.pluto.angle, self.pluto.angle], [-30, 30])
            self.ui.currPosLine2.setData([self.pluto.angle, self.pluto.angle], [-30, 30])

    def _update_arom_cursor_position(self):
        # Reset current position lines
        self.ui.currPosLine1.setData([0, 0], [-30, 30])
        self.ui.currPosLine2.setData([0, 0], [-30, 30])
        if self.data.mechanism == "HOC":
            if self.pluto.hocdisp is None: return
            # AROM position lines
            if self.data.mechanism == "HOC":
                self.ui.aromLine1.setData(
                    [self.pluto.hocdisp, self.pluto.hocdisp],
                    [-30, 30]
                )
                self.ui.aromLine2.setData(
                    [-self.pluto.hocdisp, -self.pluto.hocdisp],
                    [-30, 30]
                )
        else:
            if self.pluto.angle is None: return
            self.ui.aromLine1.setData(
                [self.pluto.angle, self.pluto.angle],
                [-30, 30]
            )
            self.ui.aromLine2.setData(
                [self.pluto.angle, self.pluto.angle],
                [-30, 30]
            )
    #
    # Graph plot initialization
    #
    def _romassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self.ui.hocGraph.setLayout(_templayout)
        _pgobj.setYRange(-20, 20)
        if self.data.mechanism == "HOC":
            _pgobj.setXRange(-10, 10)
        else:
            _pgobj.setXRange(pdef.PlutoAngleRanges[self.data.mechanism][0],
                             pdef.PlutoAngleRanges[self.data.mechanism][1])
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Current position lines
        self.ui.currPosLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        self.ui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        _pgobj.addItem(self.ui.currPosLine1)
        _pgobj.addItem(self.ui.currPosLine2)
        
        # AROM Lines
        self.ui.aromLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=2)
        )
        self.ui.aromLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=2)
        )
        _pgobj.addItem(self.ui.aromLine1)
        _pgobj.addItem(self.ui.aromLine2)
        
        # PROM Lines
        self.ui.promLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=2)
        )
        self.ui.promLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=2)
        )
        _pgobj.addItem(self.ui.promLine1)
        _pgobj.addItem(self.ui.promLine2)

    #
    # Signal Callbacks
    # 
    def _callback_pluto_newdata(self):
        # Update trial data.
        self.data.add_newdata(
            dt=self.pluto.delt(),
            pos=self.pluto.hocdisp if self.data.mechanism == "HOC" else self.pluto.angle
        )
        self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA
        )
        self.update_ui()

    def _callback_pluto_btn_released(self):
        # Run the statemachine
        apromset = self._smachine.run_statemachine(
            pdef.PlutoEvents.RELEASED
        )
        self.update_ui()
        # # Check if arom or prom is set
        # if apromset == "aromset":
        #     self.aromset.emit()
        # elif apromset == "promset":
        #     self.promset.emit()
        pass

    #
    # Control Callbacks
    #
    def _callback_trialrun_clicked(self):
        if self.data.demomode is None or self.data.demomode is False:
            self.data.demomode = not self.ui.cbTrialRun.isChecked()

    # def _callback_arom_clicked(self, event):
    #     self._smachine.run_statemachine(
    #         PlutoAPRomAssessEvent.AROM_SELECTED
    #     )
    #     self.update_ui()
    
    # def _callback_prom_clicked(self, event):
    #     self._smachine.run_statemachine(
    #         PlutoAPRomAssessEvent.PROM_SELECTED
    #     )
    #     self.update_ui()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM12")
    pcalib = PlutoAPRomAssessWindow(plutodev=plutodev, mechanism="WFE")
    pcalib.show()
    sys.exit(app.exec_())
