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
    QtWidgets,
    QtGui)
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtCore import pyqtSignal
import pyqtgraph as pg
from enum import Enum

import plutodefs as pdef
from ui_plutoapromassess import Ui_APRomAssessWindow

#
# APROM Assessment Constants
#
POS_VEL_WINDOW_LENGHT = 50
START_POS_HOC_THRESHOLD = 0.25      # cm
START_POS_NOT_HOC_THRESHOLD = 2.5   # deg
STOP_POS_HOC_THRESHOLD = 0.5        # cm
STOP_POS_NOT_HOC_THRESHOLD = 5      # deg
VEL_HOC_THRESHOLD = 1               # cm/sec
VEL_NOT_HOC_THRESHOLD = 5           # deg/sec
STOP_ZONE_DURATION_THRESHOLD = 1    # sec

#
# Display constants
#
CURSOR_LOWER_LIMIT = -30
CURSOR_UPPER_LIMIT = 10
INST_X_POSITION = 0.5
INST_Y_POSITION = 2.75


class PlutoAPRomAssessStates(Enum):
    FREE_RUNNING = 0
    TRIAL_ACTIVE_WAIT_TO_MOVE = 1
    TRIAL_ACTIVE_MOVING = 2
    TRIAL_ACTIVE_HOLDING = 3
    TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE = 4
    TRIAL_ACTIVE_NEW_ROM_SET = 5
    ROM_DONE = 6


class PlutoAPRomData(object):
    def __init__(self, mechname, romtype, ntrials):
        self._mechname = mechname
        self._romtype = romtype
        self._ntrials = ntrials
        self._demodone = None
        self._currtrial = 0
        self._startpos = None
        self._trialrom = []
        self._trialdata = {"dt": [], "pos": [], "vel": []}
        self._currtrial = -1
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
    def currtrial(self):
        return self._currtrial
    
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
    def demodone(self):
        return self._demodone
    
    @demodone.setter
    def demodone(self, value):
        self._demodone = value
    
    @property
    def in_demo_mode(self):
        return self._demodone is False
    
    @property
    def all_trials_done(self):
        """Check if all trials are done.
        """
        return self._currtrial >= self._ntrials
    
    def start_newtrial(self):
        """Start a new trial.
        """
        if self._currtrial < self._ntrials:
            self._trialdata = {"dt": [], "pos": [], "vel": []}
            self._trialrom = []
            self._startpos = None
            self._currtrial += 1

    def add_newdata(self, dt, pos):
        """Add new data to the trial data.
        """
        self._trialdata['dt'].append(dt)
        self._trialdata['pos'].append(pos)
        self._trialdata['vel'].append((pos - self._trialdata['pos'][-2]) / dt
                                      if len(self._trialdata['pos']) > 1
                                      else 0)
        if len(self._trialdata['dt']) > POS_VEL_WINDOW_LENGHT:
            self._trialdata['dt'].pop(0)
            self._trialdata['pos'].pop(0)
            self._trialdata['vel'].pop(0)
    
    def add_new_trialrom_data(self):
        """Add new value to trial ROM.
        """
        self._trialrom.append(np.mean(self._trialdata['pos']))
        # Sort trial ROM values in the ascending order.
        self._trialrom.sort()
        print("Trial ROM: ", self._trialrom)
    
    def set_rom(self):
        """Set the ROM value for the given trial.
        """
        self._rom[self._currtrial] = [self._trialrom[0], self._trialrom[-1]]
        
    def set_startpos(self):
        """Sets the start position as the average of trial data.
        """
        self._startpos = np.mean(self._trialdata['pos'])
        self._trialrom = [self._startpos]
        print("Start Pos: ", self._startpos)
        print("Trial ROM: ", self._trialrom)


class PlutoAPRomAssessmentStateMachine():
    def __init__(self, plutodev, data: PlutoAPRomData, instdisp):
        self._state = PlutoAPRomAssessStates.FREE_RUNNING
        self._statetimer = 0
        self._data = data
        self._instruction = f""
        self._instdisp = instdisp
        self._pluto = plutodev
        self._stateactions = {
            PlutoAPRomAssessStates.FREE_RUNNING: self._free_running,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE: self._trial_active_wait_to_move,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_MOVING: self._trial_active_moving,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_HOLDING: self._trial_active_holding,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE: self._trial_active_holding_stop_zone,
            PlutoAPRomAssessStates.ROM_DONE: self._rom_done
        }
        # Start a new trial.
        self._data.start_newtrial()

    @property
    def state(self):
        return self._state
    
    @property
    def in_a_trial_state(self):
        return self._state in [
            PlutoAPRomAssessStates.TRIAL_ACTIVE_MOVING,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_HOLDING,
            PlutoAPRomAssessStates.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE
        ]
    
    def reset_statemachine(self):
        self._state = PlutoAPRomAssessStates.FREE_RUNNING
        self._statetimer = 0
        self._instruction = f""
        self._data.start_newtrial()
    
    def run_statemachine(self, event, dt):
        """Execute the state machine depending on the given even that has occured.
        """
        retval = self._stateactions[self._state](event, dt)
        self._instdisp.setText(self._instruction)
        return retval

    def _free_running(self, event, dt):
        # Check if all trials are done.
        if not self._data.in_demo_mode and self._data.all_trials_done:
            self._instruction = f"{self._data.romtype} ROM Assessment Done. Press the PLUTO Button to exit."
            if event == pdef.PlutoEvents.RELEASED:
                self._state = PlutoAPRomAssessStates.ROM_DONE
                self._statetimer = 0
            return
        
        # Wait for start.
        if self._data.in_demo_mode:
            self._instruction = f"Hold and press PLUTO Button to demo trial."
        else:
            self._instruction = f"Hold and press PLUTO Button to start trial {self._data._currtrial+1}/{self._data.ntrials}."
        if event == pdef.PlutoEvents.RELEASED:
            # Make sure the joint is in rest before we can swtich.
            if self.subj_is_holding():
                self._data.set_startpos()
                self._trialrom = [] if self._data.mechanism != "HOC" else [0,]
                self._state = PlutoAPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE
                self._statetimer = 0
    
    def _trial_active_wait_to_move(self, event, dt):
        self._instruction = f"Move an hold to record ROM."
        # Check if new data.
        if event == pdef.PlutoEvents.NEWDATA:
            # Wait for the subject to away from the start position.
            if self.subj_is_holding() is False and self.away_from_start():
                self._state = PlutoAPRomAssessStates.TRIAL_ACTIVE_MOVING

    def _trial_active_moving(self, event, dt):
        self._instruction = f"Move and hold to record ROM position."
        if event == pdef.PlutoEvents.NEWDATA:
            # Nothing to do if the subject is moving.
            if self.subj_is_holding() is False: return
            # Subject is holdin away from start.
            if self.subj_in_the_stop_zone():
                # Holding in the stop zone.
                self._state = PlutoAPRomAssessStates.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE
                self._statetimer = STOP_ZONE_DURATION_THRESHOLD
            else:
                # Add the current position to trial ROM.
                self._data.add_new_trialrom_data()
                self._state = PlutoAPRomAssessStates.TRIAL_ACTIVE_HOLDING

    def _trial_active_holding(self, event, dt):
        # Check if the subject is in the stopping zone.
        self._instruction = f"{self._data.romtype} Move and hold to record ROM position."
        if event == pdef.PlutoEvents.NEWDATA:
            # Check if the subject is moving again.
            if self.subj_is_holding() is False:
                # Subject is moving again. Go back to moving state.
                self._state = PlutoAPRomAssessStates.TRIAL_ACTIVE_MOVING

    def _trial_active_holding_stop_zone(self, event, dt):
        # Check if the subject is in the stopping zone.
        if event == pdef.PlutoEvents.NEWDATA:
            if self.subj_is_holding() is True:
                self._statetimer -= dt
                self._instruction = f"Hold for {self._statetimer:2.1f}sec to stop."
                # Check if the subject is moving again.
                if self._statetimer <= 0:
                    # Done with the trial.
                    self._state = PlutoAPRomAssessStates.FREE_RUNNING
                    # Set the ROM for the current trial.
                    if not self._data.in_demo_mode:
                        self._data.set_rom()
                        self._data.start_newtrial()
            else:
                # Go back to the moving state.
                # Subject is moving again. Go back to moving state.
                self._state = PlutoAPRomAssessStates.TRIAL_ACTIVE_MOVING
    
    def _rom_done(self, event, dt):
        pass

    #
    # Supporting functions
    #
    def subj_is_holding(self):
        """Check if the subject is holding the position.
        """
        _th = (VEL_HOC_THRESHOLD
               if self._data.mechanism == "HOC"
               else VEL_NOT_HOC_THRESHOLD)
        return bool(np.all(np.abs(self._data.trialdata['vel']) < _th))
    
    def away_from_start(self):
        """Check if the subject has moved away from the start position.
        """
        if self._data.mechanism == "HOC":
            return np.abs(self._pluto.hocdisp - self._data.startpos) > START_POS_HOC_THRESHOLD
        else:
            return np.abs(self._pluto.angle - self._data.startpos) > START_POS_NOT_HOC_THRESHOLD
    
    def subj_in_the_stop_zone(self):
        """Check if the subject is in the stop zone.
        """
        if self._data.mechanism == "HOC":
            return np.abs(self._pluto.hocdisp - self._data.startpos) < STOP_POS_HOC_THRESHOLD
        else:
            return np.abs(self._pluto.angle - self._data.startpos) < STOP_POS_NOT_HOC_THRESHOLD


class PlutoAPRomAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO ROM assessment window.
    """
    romset = pyqtSignal()

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

        # Initialize graph for plotting
        self._romassess_add_graph()

        # Initialize the state machine.
        self._smachine = PlutoAPRomAssessmentStateMachine(self._pluto, self.data, self.ui.subjInst)

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
        # Check if the assessment is started without clinical trial.
        if self.data.demodone is not True:
            self.data.demodone = (self._smachine.state == PlutoAPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE
                                  and self.ui.cbTrialRun.isChecked() is False) 
        self.ui.cbTrialRun.setEnabled(self.data.demodone is not True)
        # Update the graph display
        # Current position
        self._update_current_position_cursor()
        # if self._smachine.state == PlutoAPRomAssessStates.TRIAL_ACTIVE_WAIT_TO_MOVE:
        if self._smachine.in_a_trial_state:
            self._draw_stop_zone_lines()
            self._highlight_start_zone()
            self._update_arom_cursor_position()
        elif self._smachine.state == PlutoAPRomAssessStates.FREE_RUNNING:
            # Reset arom cursor position.
            self._reset_display()
        
        # Update main text
        if self.pluto.angle is None: return
        _posstr = (f"[{self.pluto.hocdisp:5.2f}cm]" 
                   if self.data.mechanism == "HOC"
                   else f"[{self.pluto.angle:5.2f}deg]")
        self.ui.lblTitle.setText(f"PLUTO {self.data.romtype} ROM Assessment {_posstr}")

        # Update status message
        self.ui.lblStatus.setText(f"{self._smachine.state}")

        # Close if needed
        if self._smachine.state == PlutoAPRomAssessStates.ROM_DONE:
            self.close()
    
    def _update_current_position_cursor(self):
        if self.data.mechanism == "HOC":
            if self.pluto.hocdisp is None:
                return
            # Plot when there is data to be shown
            self.ui.currPosLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
            self.ui.currPosLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
        else:
            if self.pluto.angle is None:
                return
            self.ui.currPosLine1.setData([self.pluto.angle, self.pluto.angle], [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT])
            self.ui.currPosLine2.setData([self.pluto.angle, self.pluto.angle], [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT])

    def _draw_stop_zone_lines(self):
        _th = (STOP_POS_HOC_THRESHOLD
               if self.data.mechanism == "HOC"
               else STOP_POS_NOT_HOC_THRESHOLD)
        if self.data.mechanism == "HOC":
            self.ui.stopLine1.setData(
                [self.data.startpos + _th, self.data.startpos + _th],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
            self.ui.stopLine2.setData(
                [-self.data.startpos - _th, -self.data.startpos - _th],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
        else:
            self.ui.stopLine1.setData(
                [self.data.startpos - _th, self.data.startpos - _th],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
            self.ui.stopLine2.setData(
                [self.data.startpos + _th, self.data.startpos + _th],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
    
    def _update_arom_cursor_position(self):
        if len(self.data._trialrom) == 0: return
        if self.data.mechanism == "HOC":
            self.ui.romLine1.setData(
                [-self.data._trialrom[-1], -self.data._trialrom[-1]],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
            self.ui.romLine2.setData(
                [self.data._trialrom[-1], self.data._trialrom[-1]],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
            # Fill between the two AROM lines
            self.ui.romFill.setRect(-self.data._trialrom[-1],
                                    CURSOR_LOWER_LIMIT,
                                    2 * self.data._trialrom[-1],
                                    CURSOR_UPPER_LIMIT - CURSOR_LOWER_LIMIT)
        else:
            self.ui.romLine1.setData(
                [self.data._trialrom[0], self.data._trialrom[0]],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
            self.ui.romLine2.setData(
                [self.data._trialrom[-1], self.data._trialrom[-1]],
                [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
            )
            # Fill between the two AROM lines
            self.ui.romFill.setRect(self.data._trialrom[0],
                                    CURSOR_LOWER_LIMIT,
                                    self.data._trialrom[-1] - self.data._trialrom[0],
                                    CURSOR_UPPER_LIMIT - CURSOR_LOWER_LIMIT)
    
    def _highlight_start_zone(self):
        if len(self.data._trialrom) == 0: return
        # Fill the start zone
        if self._smachine.state == PlutoAPRomAssessStates.TRIAL_ACTIVE_HOLDING_IN_STOP_ZONE:
            _th = (STOP_POS_HOC_THRESHOLD 
                   if self.data.mechanism == "HOC" 
                   else STOP_POS_NOT_HOC_THRESHOLD)
            self.ui.strtZoneFill.setRect(self.data.startpos - _th,
                                         CURSOR_LOWER_LIMIT,
                                         2 * _th,
                                         CURSOR_UPPER_LIMIT - CURSOR_LOWER_LIMIT)
        else:
            self.ui.strtZoneFill.setRect(0, CURSOR_LOWER_LIMIT,
                                         0, CURSOR_UPPER_LIMIT - CURSOR_LOWER_LIMIT)
    
    def _reset_display(self):
        # Reset ROM display
        self.ui.romLine1.setData(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
        )
        self.ui.romLine2.setData(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
        )
        # Fill between the two AROM lines
        self.ui.romFill.setRect(0, CURSOR_LOWER_LIMIT,
                                0, CURSOR_UPPER_LIMIT - CURSOR_LOWER_LIMIT)
        # Reset stop zone.
        self.ui.stopLine1.setData(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
        )
        self.ui.stopLine2.setData(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT]
        )
        self.ui.strtZoneFill.setRect(0, CURSOR_LOWER_LIMIT,
                                     0, CURSOR_UPPER_LIMIT - CURSOR_LOWER_LIMIT)

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
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        self.ui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        _pgobj.addItem(self.ui.currPosLine1)
        _pgobj.addItem(self.ui.currPosLine2)
        
        # ROM Lines
        self.ui.romLine1 = pg.PlotDataItem(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FF8888',width=2)
        )
        self.ui.romLine2 = pg.PlotDataItem(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FF8888',width=2)
        )
        _pgobj.addItem(self.ui.romLine1)
        _pgobj.addItem(self.ui.romLine2)

        # ROM Fill
        self.ui.romFill = QGraphicsRectItem()
        self.ui.romFill.setBrush(QColor(255, 136, 136, 80))  # match AROM color, alpha=80
        self.ui.romFill.setPen(pg.mkPen(None))  # No border
        _pgobj.addItem(self.ui.romFill)
        
        # Stop zone Lines
        self.ui.stopLine1 = pg.PlotDataItem(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF', width=1, style=QtCore.Qt.PenStyle.DotLine)
        )
        self.ui.stopLine2 = pg.PlotDataItem(
            [0, 0],
            [CURSOR_LOWER_LIMIT, CURSOR_UPPER_LIMIT],
            pen=pg.mkPen(color = '#FFFFFF', width=1, style=QtCore.Qt.PenStyle.DotLine)
        )
        _pgobj.addItem(self.ui.stopLine1)
        _pgobj.addItem(self.ui.stopLine2)
        
        # Start zone Fill
        self.ui.strtZoneFill = QGraphicsRectItem()
        self.ui.strtZoneFill.setBrush(QColor(136, 255, 136, 80))
        self.ui.strtZoneFill.setPen(pg.mkPen(None))  # No border
        _pgobj.addItem(self.ui.strtZoneFill)
        
        # Instruction text
        self.ui.subjInst = pg.TextItem(text='', color='w', anchor=(INST_X_POSITION, INST_Y_POSITION))
        self.ui.subjInst.setPos(0, 0)  # Set position (x, y)
        # Set font and size
        self.ui.subjInst.setFont(QtGui.QFont("Bahnschrift Light", 18))
        _pgobj.addItem(self.ui.subjInst)

    #
    # Signal Callbacks
    # 
    def _callback_pluto_newdata(self):
        # Update trial data.
        self.data.add_newdata(
            dt=self.pluto.delt(),
            pos=self.pluto.hocdisp if self.data.mechanism == "HOC" else self.pluto.angle
        )
        # Run the statemachine
        self._smachine.run_statemachine(
            pdef.PlutoEvents.NEWDATA,
            dt=self.pluto.delt()
        )
        # Check if ROM assessment is complete.
        if self._smachine.state == PlutoAPRomAssessStates.FREE_RUNNING and self.data.all_trials_done: 
            self.romset.emit()
        # Update the GUI only at 1/10 the data rate
        if np.random.rand() < 0.1:
            self.update_ui()

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
        if self.data.demodone is None or self.data.demodone is False:
            self.data.demodone = not self.ui.cbTrialRun.isChecked()
            # Retart ROM assessment statemachine
            self._smachine.reset_statemachine()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM12")
    pcalib = PlutoAPRomAssessWindow(plutodev=plutodev, mechanism="HOC", ntrials=2)
    pcalib.romset.connect(lambda : print(f"ROM set: {pcalib.data.rom}"))
    pcalib.show()
    sys.exit(app.exec_())
