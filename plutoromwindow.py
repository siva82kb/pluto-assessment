"""
Module for handling the operation of the PLUTO range of motion assesmsent
window.

Author: Sivakumar Balasubramanian
Date: 04 August 2024
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
from ui_plutoromassess import Ui_RomAssessWindow


class PlutoRomAssessEvent(Enum):
    AROM_SELECTED = 0
    PROM_SELECTED = 1


class PlutoRomAssessStates(Enum):
    FREE_RUNNING = 0
    AROM_ASSESS = 1
    PROM_ASSESS = 2
    ROM_DONE = 3


class PlutoRomAssessmentStateMachine():
    def __init__(self, plutodev, aromval=-1, promval=-1):
        self._state = PlutoRomAssessStates.FREE_RUNNING
        self._arom = aromval if aromval >= 0 else 0
        self._prom = promval if promval >= 0 else 0
        self._instruction = "Assessing AROM. Press the PLUTO Button when done."
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
    def arom(self):
        return self._arom
    
    @property
    def prom(self):
        return self._prom

    @property
    def instruction(self):
        return self._instruction

    def run_statemachine(self, event):
        """Execute the state machine depending on the given even that has occured.
        """
        return self._stateactions[self._state](event)
    
    def _free_running(self, event):
        # Wait for AROM or PROM to be selected.
        if event == PlutoRomAssessEvent.AROM_SELECTED:
            self._state = PlutoRomAssessStates.AROM_ASSESS
            self._instruction = "Assessing AROM. Press the PLUTO Button when done."
            self._apromflag |= 0x01
        elif event == PlutoRomAssessEvent.PROM_SELECTED:
            self._state = PlutoRomAssessStates.PROM_ASSESS
            # print(self._state)
            self._instruction = "Assessing PROM. Press the PLUTO Button when done."
            self._apromflag |= 0x02
        # Check if both AROM and PROM have been assessed.
        if self._apromflag == 0x03:
            self._instruction = "ROM Assessment Done. Press the PLUTO Button to exit."
            if event == pdef.PlutoEvents.RELEASED:
                self._state = PlutoRomAssessStates.ROM_DONE
    
    def _arom_assess(self, event):
        # Check if the button release event has happened.
        if event == pdef.PlutoEvents.RELEASED:
            self._arom = abs(self._pluto.hocdisp)
            # Update PROM if needed
            self._prom = self._arom if self._arom > self._prom else self._prom
            # Update the instruction
            self._instruction = "Select AROM or PROM to assess."
            self._state = PlutoRomAssessStates.FREE_RUNNING
            return "aromset"
 
    def _prom_assess(self, event):
        # Check if the button release event has happened.
        if event == pdef.PlutoEvents.RELEASED:
            if abs(self._pluto.hocdisp) >= self._arom:
                self._prom = abs(self._pluto.hocdisp)
                # Update the instruction
                self._instruction = "Select AROM or PROM to assess."
                self._state = PlutoRomAssessStates.FREE_RUNNING
                return "promset"
            else:
                # Update the instruction
                self._instruction = "Error! PROM cannot be less than AROM.\nAssessing PROM. Press the PLUTO Button when done."
                pass
    
    def _rom_done(self, event):
        pass



class PlutoRomAssessWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO ROM assessment window.
    """
    aromset = pyqtSignal()
    promset = pyqtSignal()

    def __init__(self, parent=None, plutodev: QtPluto=None, mechanism: str=None, modal=False):
        """
        Constructor for the PlutoRomAssessWindow class.
        """
        super(PlutoRomAssessWindow, self).__init__(parent)
        self.ui = Ui_RomAssessWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # PLUTO device
        self._pluto = plutodev
        self._mechanism = mechanism

        # Initialize the state machine.
        self._smachine = PlutoRomAssessmentStateMachine(self._pluto)

        # Initialize graph for plotting
        self._romassess_add_graph()

        # Attach callbacks
        self.pluto.newdata.connect(self._callback_pluto_newdata)
        self.pluto.btnreleased.connect(self._callback_pluto_btn_released)

        # Attach controls callback
        self.ui.pbArom.clicked.connect(self._callback_arom_clicked)
        self.ui.pbProm.clicked.connect(self._callback_prom_clicked)

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
        # Update the graph display
        # Current position
        if self._smachine.state == PlutoRomAssessStates.FREE_RUNNING:
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
        elif self._smachine.state == PlutoRomAssessStates.AROM_ASSESS:
            self.ui.currPosLine1.setData([0, 0], [-30, 30])
            self.ui.currPosLine2.setData([0, 0], [-30, 30])
            # AROM position
            self.ui.aromLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self.ui.aromLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )
        elif self._smachine.state == PlutoRomAssessStates.PROM_ASSESS:
            self.ui.currPosLine1.setData([0, 0], [-30, 30])
            self.ui.currPosLine2.setData([0, 0], [-30, 30])
            # PROM position
            self.ui.promLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self.ui.promLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )

        # Update main text
        self.ui.label.setText(f"PLUTO ROM Assessment [{self.pluto.hocdisp:5.2f}cm]")

        # Update instruction
        self.ui.textInstruction.setText(self._smachine.instruction)

        # Update buttons
        self.ui.pbArom.setText(f"Assess AROM [{self.arom:5.2f}cm]")
        self.ui.pbProm.setText(f"Assess PROM [{self.prom:5.2f}cm]")
        self.ui.pbArom.setEnabled(
            self._smachine.state == PlutoRomAssessStates.FREE_RUNNING
        )
        self.ui.pbProm.setEnabled(
            self._smachine.state == PlutoRomAssessStates.FREE_RUNNING
        )

        # Close if needed
        if self._smachine.state == PlutoRomAssessStates.ROM_DONE:
            self.close()   

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
        _pgobj.setXRange(-10, 10)
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
        # Check if arom or prom is set
        if apromset == "aromset":
            self.aromset.emit()
        elif apromset == "promset":
            self.promset.emit()

    #
    # Control Callbacks
    #
    def _callback_arom_clicked(self, event):
        self._smachine.run_statemachine(
            PlutoRomAssessEvent.AROM_SELECTED
        )
        self.update_ui()
    
    def _callback_prom_clicked(self, event):
        self._smachine.run_statemachine(
            PlutoRomAssessEvent.PROM_SELECTED
        )
        self.update_ui()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM4")
    pcalib = PlutoRomAssessWindow(plutodev=plutodev, mechanism="HOC")
    pcalib.show()
    sys.exit(app.exec_())
