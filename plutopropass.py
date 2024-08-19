"""
QT script defininf the functionality of the PLUTO proprioception assessment window.

Author: Sivakumar Balasubramanian
Date: 24 July 2024
Email: siva82kb@gmail.com
"""

import sys
import re
import pathlib
import json
import random
import numpy as np

from qtpluto import QtPluto
from datetime import datetime as dt

from PyQt5 import (
    QtCore,
    QtWidgets,)
from PyQt5.QtCore import (
    pyqtSignal,
    QTimer,)
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QMessageBox,
    QInputDialog
)
import pyqtgraph as pg

import plutodefs as pdef
import plutostatemachines as psm

from plutodataviewwindow import PlutoDataViewWindow
from plutocalibwindow import PlutoCalibrationWindow
from plutotestwindow import PlutoTestControlWindow
from plutoromwindow import PlutoRomAssessWindow

from ui_plutopropass import Ui_PlutoPropAssessor
from ui_plutocalib import Ui_CalibrationWindow
# from ui_plutodataview import Ui_DevDataWindow
from ui_plutotestcontrol import Ui_PlutoTestControlWindow
from ui_plutoromassess import Ui_RomAssessWindow
from ui_plutopropassessctrl import Ui_ProprioceptionAssessWindow

# Module level constants.
DATA_DIR = "propassessment"
PROTOCOL_FILE = f"{DATA_DIR}/propassess_protocol.json"
PROPASS_CTRL_TIMER_DELTA = 0.01


class PlutoPropAssesor(QtWidgets.QMainWindow, Ui_PlutoPropAssessor):
    """Main window of the PLUTO proprioception assessment program.
    """
    
    def __init__(self, port, *args, **kwargs) -> None:
        """View initializer."""
        super(PlutoPropAssesor, self).__init__(*args, **kwargs)
        self.setupUi(self)

        # Move close to top left corner
        self.move(50, 100)

        # PLUTO COM
        self.pluto = QtPluto(port)
        self.pluto.newdata.connect(self._callback_newdata)
        self.pluto.btnpressed.connect(self._callback_btn_pressed)
        self.pluto.btnreleased.connect(self._callback_btn_released)
        
        # Subject details
        self._subjid = None
        self._currsess = None
        self._calib = False
        self._datadir = None
        self._romdata = {
            "AROM": 5.0,
            "PROM": 7.0
        }
        # self._romdata = {
        #     "AROM": 0.0,
        #     "PROM": 0.0
        # }
        self._propassdata = None
        self._protocol = None
        self._set_subjectid("test")
        
        # Initialize timers.
        self.apptimer = QTimer()
        self.apptimer.timeout.connect(self._callback_app_timer)
        self.apptimer.start(1000)
        self.apptime = 0
        # self.propass_dur_timer = QTimer()
        # self.propass_dur_timer.timeout.connect(self._callback_propassess_dur_timer)
        # self.propass_dur_timer.stop()
        self.propass_sm_timer = QTimer()
        self.propass_sm_timer.timeout.connect(self._callback_propassess_sm_timer)
        self.propass_sm_time = -1
        # Anothe timer for controlling the target position command to the robot.
        # We probably can get all this done with a single timer, but for the lack 
        # of time for an elegant solution, we will use an additional timer.
        self.propass_ctrl_timer = QTimer()
        self.propass_ctrl_timer.timeout.connect(self._callback_propassess_ctrl_timer)
        self.propass_tgtctrl = {
            "time": -1,
            "init": 0,
            "final": 0,
            "dur": 0,
            "curr": 0,
            "on_timer": 0,
            "off_timer": 0
        }

        # Attach callback to the buttons
        self.pbSubject.clicked.connect(self._callback_select_subject)
        self.pbCalibration.clicked.connect(self._callback_calibrate)
        self.pbTestDevice.clicked.connect(self._callback_test_device)
        self.pbRomAssess.clicked.connect(self._callback_assess_rom)
        self.pbPropAssessment.clicked.connect(self._callback_assess_prop)

        # Attach callback to other events
        # self.closeEvent = self._calibwnd_close_event

        # Other windows
        self._devdatawnd = None
        self._calibwnd = None
        self._testdevwnd = None
        self._romwnd = None
        self._propwnd = None
        self._wnddata = {}

        # State machines for new windows
        self._smachines = {
            "calib": None,
            "rom": None,
            "prop": None
        }

        # Open the device data viewer by default.
        self._open_devdata_viewer() 

        # Update UI
        self.update_ui()
    
    #
    # Controls callback
    #
    def _callback_select_subject(self):
        _subjid, _done = QInputDialog.getText(
             self,
             'Select Subject',
             'Enter subject ID:'
        )
        # Check if a valid input was given.
        if _done is False:
            return
        
        # Only alphabets and numbers are allowed.
        if re.match("^[A-Za-z0-9_-]*$", _subjid):
            # Check if the user name already exists
            _path = pathlib.Path(DATA_DIR, _subjid.lower())
            # Check if the user knows that this user name exists.
            if _path.exists():
                # Check if the user is OK with this. Else they will need to
                # create a new subject ID.
                reply = QMessageBox.question(
                    self, 'Existing Subject ID',
                    f'Subject ID: [{_subjid.lower()}] exists? Continue with this ID?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            # Set subject ID, and create the folder if needed.
            self._set_subjectid(_subjid.lower())
        
        # Write the subject details JSON file.
        self._write_subject_json()

        # update UI
        self.update_ui()
    
    def _callback_calibrate(self):
        # Calibration window and open it as a modal window.
        self._calibwnd = PlutoCalibrationWindow(plutodev=self.pluto,
                                                mechanism="HOC",
                                                modal=True)
        self._calibwnd.closeEvent = self._calibwnd_close_event
        self._calibwnd.show()
    
    def _callback_test_device(self):
        self._testdevwnd = PlutoTestControlWindow(plutodev=self.pluto,
                                                  modal=True)
        self._testdevwnd.closeEvent = self._calibwnd_close_event
        self._testdevwnd.show()

    def _callback_assess_rom(self):
        self._romwnd = PlutoRomAssessWindow(plutodev=self.pluto,
                                            mechanism="HOC",
                                            modal=True)
        # Attach to the aromset and promset events.
        self._romwnd.aromset.connect(self._callback_aromset)
        self._romwnd.promset.connect(self._callback_promset)
        self._romwnd.closeEvent = self._calibwnd_close_event
        self._romwnd.show()

    def _callback_assess_prop(self):
        # Read the protocol file.
        self._initialize_protocol()
        
        # Create a new timer and share it with the state machine.
        # Create the proprioception assessment statemachine
        self.propass_sm_timer.stop()
        self.propass_sm_time = 0
        self._smachines["prop"] = psm.PlutoPropAssessmentStateMachine(
            self.pluto,
            self._protocol,
            self.propass_sm_timer
        )
        
        # Create the window
        self._propwnd = QtWidgets.QMainWindow()
        self._wndui = Ui_ProprioceptionAssessWindow()
        self._propwnd.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self._wndui.setupUi(self._propwnd)
        
        # Add graph to the window
        self._propassess_add_graph()

        # Attach events to the controls.
        self._propwnd.closeEvent = self._propwnd_close_event
        self._wndui.pbStartStopProtocol.clicked.connect(self._callback_propprotocol_startstop)
        self._propwnd.show()
        self._update_propwnd_ui()

    # 
    # Timer callbacks
    #
    def _callback_app_timer(self):
        self.apptime += 1
        _con = self.pluto.is_connected()
        self.statusBar().showMessage(
            ' | '.join((
                f"{self.apptime:5d}s",
                _con if _con != "" else "Disconnected",
                f"FR: {self.pluto.framerate():4.1f}Hz",
                f"{self._subjid}",
            ))
        )
    
    # def _callback_propassess_dur_timer(self):
    #     self._propassdata["assessdur"] += 1

    def _callback_propassess_sm_timer(self):
        # Update trial duration
        _checkstate = not (
            self._smachines["prop"].state == psm.PlutoPropAssessStates.WAIT_FOR_START
            or self._smachines["prop"].state == psm.PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
            or self._smachines["prop"].state == psm.PlutoPropAssessStates.INTER_TRIAL_REST
            or self._smachines["prop"].state == psm.PlutoPropAssessStates.PROTOCOL_STOP
            or self._smachines["prop"].state == psm.PlutoPropAssessStates.PROP_DONE
        )
        # Act according to the state.
        if self._smachines["prop"] == psm.PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            # Check if the demo duration has been reached.
            pass


    def _callback_propassess_ctrl_timer(self):
        # Check state and act accordingly.
        self.propass_tgtctrl['time'] = (self.propass_tgtctrl['time']+ PROPASS_CTRL_TIMER_DELTA
                                        if self.propass_tgtctrl['time'] >= 0
                                        else -1)
        self.propass_sm_time = (self.propass_sm_time + PROPASS_CTRL_TIMER_DELTA
                                if self.propass_sm_time >= 0
                                else -1)
        if self._smachines["prop"].state == psm.PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            # Update target position.
            self._update_target_position()

            # Check if the target has been reached.
            _tgterr = self.propass_tgtctrl["final"] - self.pluto.hocdisp
            if abs(_tgterr) < self._protocol['target_error_th']:
                # Target reached. Wait to see if target position is maintained.
                self.propass_tgtctrl["on_timer"] += PROPASS_CTRL_TIMER_DELTA
                # Check if the target has been maintained for the required duration.
                if self.propass_tgtctrl["on_timer"] >= self._protocol['on_off_target_duration']:
                    # Target maintained. Move to next state.
                    self._smachines["prop"].run_statemachine(
                        psm.PlutoPropAssessEvents.HAPTIC_DEMO_TARGET_REACHED_TIMEOUT,
                        0
                    )
        elif self._smachines["prop"].state == psm.PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            # Check if the statemachine timer has reached the required duration.
            if self.propass_sm_time >= self._protocol['demo_duration']:
                # Demo duration reached. Move to next state.
                self._smachines["prop"].run_statemachine(
                    psm.PlutoPropAssessEvents.HAPTIC_DEMO_ON_TARGET_TIMEOUT,
                    0
                )
        else:
            self.pluto.set_control("NONE", 0)
        
        self._handle_propass_state()

    #
    # Signal callbacks
    #
    def _callback_newdata(self):
        """Update the UI of the appropriate window.
        """
        # Update data viewer window.
        self.update_ui()

        # Update calibration status
        self._calib = (self.pluto.calibration == 1)
        
        # Update other windows
        if self._propwnd is not None:
            self._smachines["prop"].run_statemachine(
                None,
                self.propass_sm_time
            )
            self._update_propwnd_ui()
    
    def _callback_btn_pressed(self):
        pass
    
    def _callback_btn_released(self):
        """
        Handle this depnding on what window is currently open.
        """
        # Prop Assessment Window
        if self._propwnd is not None:
            self._smachines["prop"].run_statemachine(
                psm.PlutoButtonEvents.RELEASED,
                self.propass_sm_time
            )
            
            # Check state and respond.
            self._handle_propass_state() 

            # Update UI
            self._update_propwnd_ui()
            return
    
    def _callback_aromset(self):
        """Set AROM."""
        self._romdata["AROM"] = self._romwnd.arom
    
    def _callback_promset(self):
        """Set PROM."""
        self._romdata["PROM"] = self._romwnd.prom

    #
    # Other callbacks
    #
    def _calibwnd_close_event(self, event):
        self._calibwnd = None
        self._wndui = None
        self._smachines["calib"] = None
    
    def _testwnd_close_event(self, event):
        self._testwnd = None
        self._wndui = None

    def _romwnd_close_event(self, event):
        # Write the subject details JSON file.
        self._write_subject_json()
        # Reset variables
        self._romwnd = None
        self._wndui = None
        self._smachines["rom"] = None

    def _propwnd_close_event(self, event):
        # Set device to no control.
        self.pluto.set_control("NONE", 0)
        # Reset variables
        self._propwnd = None
        self._wndui = None
        self._smachines["prop"] = None

    #
    # UI Update function
    #
    def update_ui(self):
        # Disable buttons if needed.
        self.pbSubject.setEnabled(self._subjid is None)
        self.pbTestDevice.setEnabled(self._subjid is not None and self._calib is True)
        self.pbRomAssess.setEnabled(self._subjid is not None and self._calib is True)
        self.pbPropAssessment.setEnabled(
            self._subjid is not None 
            and self._calib is True
            and self._romdata["AROM"] > 0
            and self._romdata["PROM"] > 0
        )

        # Calibration button
        if self._calib is False:
            self.pbCalibration.setText(f"Calibrate")
        else:
            self.pbCalibration.setText("Recalibrate")
        
        # Subject ID button
        if self._subjid is not None:
            self.pbSubject.setText(f"Subject: {self._subjid} [{self._currsess}]")
        else:
            self.pbSubject.setText("Select Subject")
        
        # Update ROM values on button text.
        if self._romdata["AROM"] > 0 and self._romdata["PROM"] > 0:
            self.pbRomAssess.setText(f"Assess ROM [AROM: {self._romdata['AROM']:5.2f}cm | PROM: {self._romdata['PROM']:5.2f}cm]")
        else:
            self.pbRomAssess.setText("Assess ROM")

    #
    # Supporting functions
    #
    def _set_subjectid(self, subjid):
        self._subjid = subjid
        self._currsess = dt.now().strftime("%Y-%m-%d-%H-%M-%S")
        # set data dirr and create if needed.        
        self._datadir = pathlib.Path(DATA_DIR, self._subjid, self._currsess)
        self._datadir.mkdir(exist_ok=True, parents=True)
    
    #
    # Calibration Window Functions
    #
    def _update_calibwnd_ui(self):
        # Update based on the current state of the Calib statemachine
        if self._smachines['calib'].state == psm.PlutoCalibStates.WAIT_FOR_ZERO_SET:
            self._wndui.lblCalibStatus.setText("Not done.")
            self._wndui.lblHandDistance.setText("- NA- ")
            self._wndui.lblInstruction2.setText("Press the PLUTO button set zero.")
        elif self._smachines['calib'].state == psm.PlutoCalibStates.WAIT_FOR_ROM_SET:
            self._wndui.lblCalibStatus.setText("Zero set.")
            self._wndui.lblHandDistance.setText(f"{self.pluto.hocdisp:5.2f}cm")
            self._wndui.lblInstruction2.setText("Press the PLUTO button set ROM.")
        elif self._smachines['calib'].state == psm.PlutoCalibStates.WAIT_FOR_CLOSE:
            self._wndui.lblCalibStatus.setText("All Done!")
            self._wndui.lblHandDistance.setText(f"{self.pluto.hocdisp:5.2f}cm")
            self._wndui.lblInstruction2.setText("Press the PLUTO button to close window.")
        elif self._smachines['calib'].state == psm.PlutoCalibStates.CALIB_ERROR:
            self._wndui.lblCalibStatus.setText("Error!")
            self._wndui.lblInstruction2.setText("Press the PLUTO button to close window.")
        else:
            self._calibwnd.close()
    
    def _update_testwnd_ui(self):
        _nocontrol = not (self._wndui.radioTorque.isChecked()
                          or self._wndui.radioPosition.isChecked())
        self._wndui.hSliderTgtValue.setEnabled(not _nocontrol)
        # Check the status of the radio buttons.
        if _nocontrol:
            self._wndui.lblTargetValue.setText(f"No Control Selected")
        else:
            # Set the text based on the control selected.
            _str = "Target Value: "
            _ctrl = "TORQUE" if self._wndui.radioTorque.isChecked() else "POSITION"
            _str += f"[{pdef.PlutoTargetRanges[_ctrl][0]:3.0f}, {pdef.PlutoTargetRanges[_ctrl][1]:3.0f}]"
            _str += f" {self._pos2tgt(self._wndui.hSliderTgtValue.value()):-3.1f}Nm"
            self._wndui.lblTargetValue.setText(_str)
    
    def _update_romwnd_ui(self):
        # Update the graph display
        # Current position
        if self._smachines["rom"].state == psm.PlutoRomAssessStates.FREE_RUNNING:
            self._wndui.currPosLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self._wndui.currPosLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )
        elif self._smachines["rom"].state == psm.PlutoRomAssessStates.AROM_ASSESS:
            self._wndui.currPosLine1.setData([0, 0], [-30, 30])
            self._wndui.currPosLine2.setData([0, 0], [-30, 30])
            # AROM position
            self._wndui.aromLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self._wndui.aromLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )
        elif self._smachines["rom"].state == psm.PlutoRomAssessStates.PROM_ASSESS:
            self._wndui.currPosLine1.setData([0, 0], [-30, 30])
            self._wndui.currPosLine2.setData([0, 0], [-30, 30])
            # PROM position
            self._wndui.promLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self._wndui.promLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )

        # Udpate based on the current state of the ROM statemachine
        if self._wndui is None:
            return
        
        # Window still exists.
        self._wndui.textInstruction.setText(self._smachines['rom'].instruction)
        self._wndui.label.setText(f"PLUTO ROM Assessment [{self.pluto.hocdisp:5.2f}cm]")
        self._wndui.pbArom.setText(f"Assess AROM [{self._romdata['AROM']:5.2f}cm]")
        self._wndui.pbProm.setText(f"Assess PROM [{self._romdata['PROM']:5.2f}cm]")
        self._wndui.pbArom.setEnabled(
            self._smachines['rom'].state == psm.PlutoRomAssessStates.FREE_RUNNING
        )
        self._wndui.pbProm.setEnabled(
            self._smachines['rom'].state == psm.PlutoRomAssessStates.FREE_RUNNING
        )

        # Close if needed
        if self._smachines['rom'].state == psm.PlutoRomAssessStates.ROM_DONE:
            self._romwnd.close()
    
    def _update_propwnd_ui(self):
        # Update current hand position
        self._wndui.currPosLine1.setData(
            [self.pluto.hocdisp, self.pluto.hocdisp],
            [-30, 30]
        )
        self._wndui.currPosLine2.setData(
            [-self.pluto.hocdisp, -self.pluto.hocdisp],
            [-30, 30]
        )
        # Update target position when needed.
        _checkstate = not (
            self._smachines["prop"].state == psm.PlutoPropAssessStates.WAIT_FOR_START
            or self._smachines["prop"].state == psm.PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START
            or self._smachines["prop"].state == psm.PlutoPropAssessStates.INTER_TRIAL_REST
            or self._smachines["prop"].state == psm.PlutoPropAssessStates.PROTOCOL_STOP
            or self._smachines["prop"].state == psm.PlutoPropAssessStates.PROP_DONE
        )
        _tgt = (self._propassdata['targets'][self._propassdata['trialno']]
                if _checkstate else 0)
        # Update target line        
        self._wndui.tgtLine1.setData(
            [_tgt, _tgt],
            [-30, 30]
        )
        self._wndui.tgtLine2.setData(
            [-_tgt, -_tgt],
            [-30, 30]
        )

        # Update based on state
        _assesssdurstr = f"{self.apptime - self._propassdata['assessstarttime']:5d}sec"
        if self._smachines["prop"].state == psm.PlutoPropAssessStates.WAIT_FOR_START:
            self._wndui.pbStartStopProtocol.setText("Start Protocol")
            self._wndui.textInformation.setText("\n".join((
                "",
                self._smachines['prop'].instruction
            )))
            self._wndui.checkBoxPauseProtocol.setEnabled(False)
        elif self._smachines["prop"].state == psm.PlutoPropAssessStates.WAIT_FOR_HAPTIC_DISPAY_START:
            self._wndui.pbStartStopProtocol.setText("Stop Protocol")
            self._wndui.textInformation.setText("\n".join((
                _assesssdurstr,
                self._smachines['prop'].instruction
            )))
            self._wndui.checkBoxPauseProtocol.setEnabled(False)
            self._wndui.textInformation.setText("\n".join((
                _assesssdurstr,
                self._get_trial_details_line("Waiting for Haptic Demo"),
                self._smachines['prop'].instruction
            )))
        elif self._smachines["prop"].state == psm.PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            self._wndui.textInformation.setText("\n".join((
                _assesssdurstr,
                self._get_trial_details_line("Haptic Demo"),
                "Moving to target position."
            )))
        elif self._smachines["prop"].state == psm.PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            self._wndui.textInformation.setText("\n".join((
                _assesssdurstr,
                self._get_trial_details_line("Haptic Demo"),
                "Demonstraing Haptic Position."
            )))
      
    def _propassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self._wndui.hocGraph.setLayout(_templayout)
        _pgobj.setYRange(-20, 20)
        _pgobj.setXRange(-10, 10)
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Current position lines
        self._wndui.currPosLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        self._wndui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        _pgobj.addItem(self._wndui.currPosLine1)
        _pgobj.addItem(self._wndui.currPosLine2)
        
        # AROM Lines
        self._wndui.aromLine1 = pg.PlotDataItem(
            [self._romdata["AROM"], self._romdata["AROM"]],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        self._wndui.aromLine2 = pg.PlotDataItem(
            [-self._romdata["AROM"], -self._romdata["AROM"]],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self._wndui.aromLine1)
        _pgobj.addItem(self._wndui.aromLine2)
        
        # PROM Lines
        self._wndui.promLine1 = pg.PlotDataItem(
            [self._romdata["PROM"], self._romdata["PROM"]],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        self._wndui.promLine2 = pg.PlotDataItem(
            [-self._romdata["PROM"], -self._romdata["PROM"]],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self._wndui.promLine1)
        _pgobj.addItem(self._wndui.promLine2)
        
        # Target Lines
        self._wndui.tgtLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        self._wndui.tgtLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        _pgobj.addItem(self._wndui.tgtLine1)
        _pgobj.addItem(self._wndui.tgtLine2)
    
    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               pos=(50, 300))
        self._devdatawnd.show()

    #
    # Proprioception Assessment Window Controls
    # 
    def _callback_propprotocol_startstop(self, event):
        # Check if this is a start or stop event.
        if self._smachines["prop"].state == psm.PlutoPropAssessStates.WAIT_FOR_START:
            # Start start time
            self._propassdata["assessstarttime"] = self.apptime
            # Start event
            self._smachines["prop"].run_statemachine(
                psm.PlutoPropAssessEvents.STARTSTOP_CLICKED,
                self.propass_sm_time
            )
        else:
            # Stop event
            self.propass_dur_timer.stop()
            self._smachines["prop"].run_statemachine(
                psm.PlutoPropAssessEvents.STARTSTOP_CLICKED,
                self.propass_sm_time
            )
        self._update_propwnd_ui()
    
    def _initialize_protocol(self):
        # Read the protocol file.
        with open(PROTOCOL_FILE, "r") as fh:
            self._protocol = json.load(fh)
        
        # Start time and Trial related varaibles.
        self._propassdata = {
            'assessstarttime': 0,
            'trialstarttime': 0,
            'trialno': 0,
            'trialfile': 0,
        }
        
        # Set sutiable targets.
        self._generate_propassess_targets()

    def _generate_propassess_targets(self):
        _tgtsep = self._protocol['targets'][0] * self._romdata['PROM']
        _tgts = (self._protocol['targets']
                 if _tgtsep >= self._protocol['min_target_sep']
                 else self._protocol['targets'][1:2])
        # Generate the randomly order targets
        _tgt2 = 2 * _tgts
        _tgt3 = (self._protocol['N'] - 2) * _tgts
        random.shuffle(_tgt2)
        random.shuffle(_tgt3)
        self._propassdata['targets'] = self._romdata['PROM'] * np.array(_tgt2 + _tgt3)

    def _get_trial_details_line(self, state="Haptic Demo"):
        _nt = self._propassdata['trialno']
        _tgt = self._propassdata['targets'][_nt]
        _tdur = self.apptime - self._propassdata['trialstarttime']
        _strs = [f"Trial: {_nt:3d}", 
                 f"Target: {_tgt:5.1f}cm", 
                 f"{state:<25s}", 
                 f"Trial Dur: {_tdur:02d}sec"]
        # Add on target time when needed.
        if self.propass_sm_time >= 0:
            _strs.append(f"On Target Dur: {int(self.propass_sm_time):02d}sec")
        return " | ".join(_strs)
    
    def _handle_propass_state(self):
        # Check the state and respond accordingly.
        if self._smachines["prop"].state == psm.PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY_MOVING:
            # Check if timer has been started already.
            if self.propass_tgtctrl["time"] < 0:
                self.propass_tgtctrl["time"] = 0
                self.propass_tgtctrl["init"] = self.pluto.hocdisp
                self.propass_tgtctrl["final"] = self._propassdata['targets'][self._propassdata['trialno']]
                self.propass_tgtctrl["curr"] = self.pluto.hocdisp
                self.propass_tgtctrl["dur"] = (self.propass_tgtctrl["final"] - self.propass_tgtctrl["init"]) / self._protocol['move_speed']
                self.propass_ctrl_timer.start(int(PROPASS_CTRL_TIMER_DELTA * 1000))
                # Initialize the propass state machine time
                self.propass_sm_time = -1
        elif self._smachines["prop"].state == psm.PlutoPropAssessStates.TRIAL_HAPTIC_DISPLAY:
            # Initialize the statemachine timer if needed.
            if self.propass_sm_time == -1:
                self.propass_sm_time = 0.
        elif self._smachines["prop"].state == psm.PlutoPropAssessStates.INTRA_TRIAL_REST:
            # Initialize the statemachine timer if needed.
            if self.propass_sm_time == -1:
                self.propass_sm_time = 0.
        else:
            self.propass_ctrl_timer.stop()
    
    def _update_target_position(self):
        _t, _init, _tgt, _dur = (self.propass_tgtctrl["time"],
                                     self.propass_tgtctrl["init"],
                                     self.propass_tgtctrl["final"],
                                     self.propass_tgtctrl["dur"])
        self.propass_tgtctrl["curr"] = max(
                min(_init + (_tgt - _init) * (_t / _dur), _tgt), _init
            )
            # Send command to the robot.
        self.pluto.set_control("POSITION", -self.propass_tgtctrl["curr"] / pdef.HOCScale)

    #
    # Main window close event
    # 
    def closeEvent(self, event):
        # Set device to no control.
        self.pluto.set_control("NONE", 0)

        # Close the data viewer window
        if self._devdatawnd is not None:
            self._devdatawnd.close()

    #
    # Data logging fucntions
    #
    def _write_subject_json(self):
        _subjdata = {
            "SubjectID": self._subjid,
            "Session": self._currsess,
            "ROM": self._romdata,
            "Protocol": self._protocol,
            "PropAssessment": self._propassdata
        }
        with open(self._datadir / "session_details.json", "w") as _f:
            json.dump(_subjdata, _f, indent=4)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoPropAssesor("COM4")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())