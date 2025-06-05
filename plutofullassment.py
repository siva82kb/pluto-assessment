"""
QT script defining the functionality of the PLUTO full assessment main window.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

import itertools
import random
import sys
import re
import pathlib
import json
import numpy as np
import pandas as pd

from enum import Enum

from qtpluto import QtPluto
from datetime import datetime as dt

from PyQt5 import (
    QtWidgets,)
from PyQt5.QtCore import (
    QTimer,)
from PyQt5.QtWidgets import (
    QMessageBox,
    QInputDialog
)
from PyQt5 import QtCore, QtGui, QtWidgets

from plutodataviewwindow import PlutoDataViewWindow
from plutocalibwindow import PlutoCalibrationWindow
from plutotestwindow import PlutoTestControlWindow
from plutoapromwindow import PlutoAPRomAssessWindow
from plutoromwindow import PlutoRomAssessWindow
from plutopropassesswindow import PlutoPropAssessWindow

from ui_plutofullassessment import Ui_PlutoFullAssessor

import plutodefs as pdef
import plutofullassessdef as pfadef
from plutofullassessstatemachine import PlutoFullAssessmentStateMachine
from plutofullassessstatemachine import Events, States
from plutofullassesssdata import PlutoAssessmentData
from plutofullassesssdata import PlutoAssessmentProtocolData
from plutoassistpromwindow import PlutoAssistPRomAssessWindow
from plutodiscreachwindow import PlutoDiscReachAssessWindow
from plutopropassesswindow import PlutoPropAssessWindow
from plutofullassesssdata import DataFrameModel


DEBUG = True


class PlutoFullAssesor(QtWidgets.QMainWindow, Ui_PlutoFullAssessor):
    """Main window of the PLUTO proprioception assessment program.
    """
    
    def __init__(self, port, *args, **kwargs) -> None:
        """View initializer."""
        super(PlutoFullAssesor, self).__init__(*args, **kwargs)
        self.setupUi(self)

        # Move close to top left corner
        self.move(50, 100)

        # PLUTO COM
        self.pluto: QtPluto = QtPluto(port)
        self.pluto.newdata.connect(self._callback_newdata)
        self.pluto.btnpressed.connect(self._callback_btn_pressed)
        self.pluto.btnreleased.connect(self._callback_btn_released)

        # Get the version and device information
        self.pluto.get_version()
        self.pluto.start_sensorstream()

        # Assessment data
        self.data:PlutoAssessmentData  = PlutoAssessmentData()

        # Initialize timers.
        self.apptimer = QTimer()
        self.apptimer.timeout.connect(self._callback_app_timer)
        self.apptimer.start(1000)
        self.apptime = 0
        # Heartbeat timer
        self.heartbeattimer = QTimer()
        self.heartbeattimer.timeout.connect(lambda: self.pluto.send_heartbeat())
        self.heartbeattimer.start(250)

        # Initialize the state machine.
        self._smachine = PlutoFullAssessmentStateMachine(
            plutodev=self.pluto,
            data=self.data,
            progconsole=self.textProtocolDetails
        )
        if DEBUG:
            self._smachine.run_statemachine(Events.SUBJECT_SET, 
                                            {"subjid": "1234"})
            _data = {"type": "Stroke", "limb": "Left"}
            self._smachine.run_statemachine(Events.TYPE_LIMB_SET,
                                            _data)
            # Set limb in the device.
            self.pluto.send_heartbeat()
            self.pluto.set_limb(self.data.limb)
            # Set limb and type.
            self.cbLimb.setCurrentText(_data["limb"])
            self.cbSubjectType.setCurrentText(_data["type"])

        # Attach callback to the buttons
        self.pbSubject.clicked.connect(self._callback_select_subject)
        self.pbSetLimb.clicked.connect(self._callback_typelimb_set)
        self.pbCalibrate.clicked.connect(self._callback_calibrate)
        self.pbAROM.clicked.connect(self._callback_assess_arom)
        self.pbPROM.clicked.connect(self._callback_assess_prom)
        self.pbAPROM.clicked.connect(self._callback_assess_aprom)
        self.pbDiscReach.clicked.connect(self._callback_disc_reach)
        self.pbProp.clicked.connect(self._callback_assess_prop)
        self.rbWFE.clicked.connect(self._callback_mech_selected)
        self.rbFPS.clicked.connect(self._callback_mech_selected)
        self.rbHOC.clicked.connect(self._callback_mech_selected)
        self.pbStartMechAssessment.clicked.connect(self._callback_start_mech_assess)
        
        # Other windows
        self._devdatawnd = None
        self._calibwnd = None
        self._testdevwnd = None
        self._romwnd = None
        self._discwnd = None
        self._propwnd = None
        self._currwndclosed = True
        self._wnddata = {}

        # State machines for new windows
        self._smachines = {
            "calib": None,
            "rom": None,
            "prop": None
        }

        # Open the device data viewer by default.
        # self._open_devdata_viewer() 

        # Update UI 
        # A flag to disable the main window when another window is open.
        self._maindisable = False
        self._updatetable = True
        self.update_ui()

        # One time set up
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(10)
        self.rbWFE.setFont(font)
        self.rbFPS.setFont(font)
        self.rbHOC.setFont(font)
    
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
            _path = pathlib.Path(pfadef.DATA_DIR, _subjid.lower())
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
            # Run the state machine.
            self._smachine.run_statemachine(
                Events.SUBJECT_SET,  
                {'subjid': _subjid.lower()}
            )
        
        # update UI
        self.update_ui()
    
    def _callback_typelimb_set(self):
        # Check the text of the button.
        if self.pbSetLimb.text() == "Reset Limb":
            return
        # Open dialog to confirm limb selection (Ok or cancel).
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"{self.cbSubjectType.currentText()} type and {self.cbLimb.currentText()} limb selected.\nDo you want to continue?",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply == QMessageBox.Ok:
            self._subjdetails["type"] = self.cbSubjectType.currentText()
            self._subjdetails["slimb"] = self.cbLimb.currentText()
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.TYPE_LIMB_SET,
            0
        )
        # Update UI
        self.update_ui()
    
    def _callback_calibrate(self):
        # Disable main controls
        self._maindisable = True
        # Calibration window and open it as a modal window.
        self._calibwnd = PlutoCalibrationWindow(plutodev=self.pluto,
                                                mechanism=self.data.protocol.mech,
                                                limb=self.data.limb,
                                                modal=True,
                                                onclosecb=self._calibwnd_close_event)
        self._calibwnd.show()
        self._currwndclosed = False
    
    def _callback_test_device(self):
        # Disable main controls
        self._maindisable = True
        self._testdevwnd = PlutoTestControlWindow(plutodev=self.pluto,
                                                  modal=True)
        self._testdevwnd.closeEvent = self._testwnd_close_event
        self._testdevwnd.show()

    def _callback_assess_arom(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        if self._reassess_requested("AROM") is False:
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.AROM_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._romwnd = PlutoAPRomAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.data.protocol.mech,
                "romtype": pfadef.ROMType.ACTIVE,
                "session": self.data.session,
                "ntrials": pfadef.protocol["AROM"]["N"],
                "rawfile": self.data.protocol.rawfilename,
                "summaryfile": self.data.protocol.summaryfilename,
            },
            modal=True,
            onclosecb=self._aromwnd_close_event
        )
        self._romwnd.show()
        self._currwndclosed = False

    def _callback_assess_prom(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        if self._reassess_requested("PROM") is False:
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.PROM_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._romwnd = PlutoAPRomAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.data.protocol.mech,
                "romtype": pfadef.ROMType.PASSIVE,
                "session": self.data.session,
                "ntrials": pfadef.protocol["PROM"]["N"],
                "rawfile": self.data.protocol.rawfilename,
                "summaryfile": self.data.protocol.summaryfilename,
                "arom": self.data.romsumry["AROM"][self.data.protocol.mech][-1]["rom"]
            },
            modal=True,
            onclosecb=self._promwnd_close_event
        )
        self._romwnd.show()
        self._currwndclosed = False

    def _callback_assess_aprom(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        if self._reassess_requested("APROM") is False:
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.APROM_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._romwnd = PlutoAssistPRomAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.data.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.protocol["APROM"]["N"],
                "rawfile": self.data.protocol.rawfilename,
                "summaryfile": self.data.protocol.summaryfilename,
                "arom": self.data.romsumry["AROM"][self.data.protocol.mech][-1]["rom"]
            },
            modal=True,
            onclosecb=self._apromwnd_close_event
        )
        self._romwnd.show()
        self._currwndclosed = False
    
    def _callback_disc_reach(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        if self._reassess_requested("DISC") is False:
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.DISCREACH_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._discwnd = PlutoDiscReachAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "subjid": self.data.subjid,
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.data.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.protocol["DISC"]["N"],
                "rawfile": self.data.protocol.rawfilename,
                "summaryfile": self.data.protocol.summaryfilename,
                "arom": self.data.romsumry["AROM"][self.data.protocol.mech][-1]["rom"]
            },
            modal=True,
            onclosecb=self._discreachwnd_close_event
        )
        self._discwnd.show()
        self._currwndclosed = False

    def _callback_assess_prop(self):
        # Check if PROP has already been assessed and needs to be reassessed.
        if self._reassess_requested("PROP") is False:
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.PROP_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._discwnd = PlutoPropAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "subjid": self.data.subjid,
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.data.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.protocol["DISC"]["N"],
                "rawfile": self.data.protocol.rawfilename,
                "summaryfile": self.data.protocol.summaryfilename,
                "arom": self.data.romsumry["AROM"][self.data.protocol.mech][-1]["rom"],
                "prom": self.data.romsumry["PROM"][self.data.protocol.mech][-1]["rom"]
            },
            modal=True,
            onclosecb=self._propasswnd_close_event
        )
        self._discwnd.show()
        self._currwndclosed = False

    def _callback_subjtype_select(self):
        # Reset AROM and PROM values if the current selection is different.
        if (self._subjdetails["type"] != self.cbSubjectType.currentText()):
            self._romdata["AROM"] = 0
            self._romdata["PROM"] = 0
        self._subjdetails["type"] = self.cbSubjectType.currentText()
        # Reset the limb and grip type.
        self._subjdetails["limb"] = ""
        self.cbLimb.setCurrentIndex(0)
        self._subjdetails["grip"] = ""
        self.update_ui()
    
    def _callback_mech_selected(self):
        self.update_ui()
    
    def _callback_start_mech_assess(self):
        # Check if the chosen mechanism is already assessed.
        _mechchosen = self._get_chosen_mechanism()
        if self.data.protocol.is_mechanism_assessed(_mechchosen):
            # Ask if the user wants to continue with this mechanism.
            reply = QMessageBox.question(
                self,
                "Confirm",
                f"Mechanism [{_mechchosen}] already assessed.\nDo you want to continue?",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                # Cancel the radio button selection.
                self._reset_mech_selection()
                return
        # Message box to inform the user that the mechanism is selected.
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Start {_mechchosen} assessment?\n\n",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply == QMessageBox.Cancel:
            # Cancel the radio button selection.
            self._reset_mech_selection()
            return
        # Run the state machine.
        # Get the appropriate event.
        self._smachine.run_statemachine(
            self._get_chosen_mechanism_event(),
            {}
        )
        self.update_ui()
    
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
                f"{self.data.subjid}",
                f"{self._smachine.state.name:<20}",
            ))
        )
    
    #
    # Signal callbacks
    #
    def _callback_newdata(self):
        """Update the UI of the appropriate window.
        """
        # Update PLUTO data display.
        if np.random.rand() < 0.05:
            self._display_pluto_data()
        # Update data viewer window.
        if np.random.rand() < 0.1:
            self.update_ui()
            
    def _callback_btn_pressed(self):
        pass
    
    def _callback_btn_released(self):
        pass
    
    def _callback_promset(self):
        """Set PROM."""
        self._romdata["PROM"] = self._romwnd.prom

    #
    # Other callbacks
    #
    def _calibwnd_close_event(self, data=None):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._calibwnd = None
            return
        # Window not closed.
        # Reenable main controls
        self._maindisable = False
        # Check of the calibration was successful.
        if (pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism) == self.data.protocol.mech
            and self.pluto.calibration == 1):
            # Run the state machine.
            self._smachine.run_statemachine(
                Events.CALIB_DONE if data["done"] else Events.CALIB_NO_DONE,
                {"mech": pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism)}
            )
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _testwnd_close_event(self, data=None):
        self._testdevwnd = None
        # Reenable main controls
        self._maindisable = False

    def _aromwnd_close_event(self, data=None):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._romwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.AROM_DONE if data["done"] else Events.AROM_NO_DONE,
            {"romval": data["rom"]}
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _promwnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._romwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.PROM_DONE if data["done"] else Events.PROM_NO_DONE,
            {"romval": data["rom"]}
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _apromwnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._romwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.APROM_DONE if data["done"] else Events.APROM_NO_DONE,
            {"romval": data["rom"]}
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _discreachwnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._discwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.DISCREACH_DONE if data["done"] else Events.DISCREACH_NO_DONE,
            {}
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _propasswnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._discwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.PROP_DONE if data["done"] else Events.PROP_NO_DONE,
            {}
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()

    # def _propwnd_close_event(self, data):
    #     # Set device to no control.
    #     self.pluto.set_control_type("NONE")
    #     # Reset variables
    #     self._propwnd.close()
    #     self._propwnd.deleteLater()
    #     self._propwnd = None
    #     # Reenable main controls
    #     self._maindisable = False

    #
    # UI Update function
    #
    def update_ui(self):        
        # Select subject
        self.pbSubject.setEnabled(self._maindisable is False and self._smachine.state == States.SUBJ_SELECT)
        
        # Limb selection
        _lmbflag = self._maindisable is False and self._smachine.state == States.LIMB_SELECT
        self.lblSubjectType.setEnabled(_lmbflag)
        self.cbSubjectType.setEnabled(_lmbflag)
        self.lblLimb.setEnabled(_lmbflag)
        self.cbLimb.setEnabled(_lmbflag)
        
        # Set limb button
        self.pbSetLimb.setEnabled(self.cbLimb.currentText() != "" and self.cbSubjectType.currentText() != "")

        # Update the table.
        if self.data.protocol.df is not None and self._updatetable: 
            self.tableProtocolProgress.setModel(DataFrameModel(self.data.protocol.df))
            # Optional: also shrink rows to contents
            self.tableProtocolProgress.resizeRowsToContents()
            # Set fixed row height for uniformity
            self.tableProtocolProgress.verticalHeader().setDefaultSectionSize(20)
            self._updatetable = False

        # Mechanisms selection
        _mechflag = (
            self._maindisable is False and 
            (self._smachine.state == States.MECH_SELECT
             or self._smachine.state == States.MECH_OR_TASK_SELECT)
        )
        if self.pbSetLimb.text() == "Set Limb": self.pbSetLimb.setText("Reset Limb")
        self.gbMechanisms.setEnabled(_mechflag)
        
        # Enable the appropriate mechanisms.
        self._update_mech_controls()

        # Check if any mechanism is selected to enable the mechanism assessment start button.
        self.pbStartMechAssessment.setEnabled(self._any_mechanism_selected())

        # Enable the calibration button.
        self.pbCalibrate.setEnabled(self._maindisable is False and self.data.protocol.mech is not None)
        if self.pbCalibrate.isEnabled():
            self.pbCalibrate.setStyleSheet(
                pfadef.SS_COMPLETE if self.data.protocol.calibrated 
                else pfadef.SS_INCOMPLETE
            )
        else:
            self.pbCalibrate.setStyleSheet("")

        # Enable the task buttons.
        self._update_task_controls()
        
        # Update session information.
        self.lblSessionInfo.setText(self._get_session_info()) 
        
        # if self._smachine.state == States.SUBJ_SELECT:
        #     # Disable everything except subject selection button.

        # # Select limb
        # enbflag = (self._maindisable is False 
        #            and self.data.subjid is not None 
        #            and self._mech is not None
        #            and self._mechdata[self._mech] is not None)
        # # Disable buttons if needed.
        # self.pbTestDevice.setEnabled(self._maindisable is False and self.data.subjid is None)
        # self.pbCalibrate.setEnabled(self._maindisable is False)
        # self.cbSubjectType.setEnabled(enbflag)
        # self.cbLimb.setEnabled(enbflag and self.cbSubjectType.currentText() != "")
        # self.pbPropAssess.setEnabled(enbflag)

        # # Calibration button
        # if self._calib is False:
        #     self.pbCalibrate.setText(f"Calibrate")
        # else:
        #     self.pbCalibrate.setText("Recalibrate")
        
        # # Subject ID button
        # if self.data.subjid is not None:
        #     if self._datadir is not None:
        #         self.pbSubject.setText(f"Subject: {self.data.subjid} [{self._datadir.as_posix().split('/')[-1]}]")
        #     else:
        #         self.pbSubject.setText(f"Subject: {self.data.subjid} []")
        # else:
        #     self.pbSubject.setText("Select Subject")
        
        # # Update ROM values on button text.
        # if self._romdata["AROM"] > 0 and self._romdata["PROM"] > 0:
        #     self.pbRomAssess.setText(f"Assess ROM [AROM: {self._romdata['AROM']:5.2f}cm | PROM: {self._romdata['PROM']:5.2f}cm]")
        # else:
        #     self.pbRomAssess.setText("Assess ROM")

    #
    # Supporting functions
    #
    def _get_session_info(self):
        _str = [
            f"{'' if self.data.session is None else self.data.session:<20}",
            f"{'' if self.data.subjid is None else self.data.subjid:<8}",
            f"{self.data.type if self.data.type is not None else '':<8}",
            f"{self.data.limb if self.data.limb is not None else '':<8}",
            # f"{self.data.mech if self.data.mech is not None else '':<8}",
            # f"{self.data.task if self.data.task is not None else '':<8}",
        ]
        return ":".join(_str)
    
    def _reassess_requested(self, task):
        """
        """
        if task not in self.data.protocol.task_enabled[:-1]:
            return True
        # Ask the experimenter if this assessment is to be repeated.
        reply = QMessageBox.question(
            self,
            "Reassessment Confirmation",
            f"{task} has been assessed before.\nDo you want to reassess?",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        return reply == QMessageBox.Ok

    def _update_mech_controls(self):
        # Update the text of the radio buttons.
        _mctrl = {
            "WFE": self.rbWFE,
            "FPS": self.rbFPS,
            "HOC": self.rbHOC
        }
        # Update complete/incomplete status of the mechanisms.
        for i, _m in enumerate(self.data.protocol.mech_enabled):
            _mctrl[_m].setEnabled(True)
            if _m in self.data.protocol.mech_completed:
                _mctrl[_m].setText(f"{pfadef.mech_labels[_m]} [C]")
                _mctrl[_m].setStyleSheet(pfadef.SS_COMPLETE)
            else:
                _mctrl[_m].setText(f"{pfadef.mech_labels[_m]}")
                _mctrl[_m].setStyleSheet(pfadef.SS_INCOMPLETE)
        
    def _update_task_controls(self):
        _tctrl = {
            "AROM": self.pbAROM,
            "PROM": self.pbPROM,
            "APROM": self.pbAPROM,
            "DISC": self.pbDiscReach,
            "PROP": self.pbProp,
            "FCTRL": self.pbForceCtrl,
        }
        # Go through all tasks for the mechanism and enable/disable them appropriately.
        for i, _t in enumerate(pfadef.tasks):
            if self.data.protocol.calibrated and _t in self.data.protocol.task_enabled:
                _tctrl[_t].setEnabled(True)
                if _t in self.data.protocol.task_completed:
                    _tctrl[_t].setText(f"{pfadef.task_labels[_t]} [C]")
                    _tctrl[_t].setStyleSheet(pfadef.SS_COMPLETE)
                else:
                    _tctrl[_t].setText(f"{pfadef.task_labels[_t]}")
                    _tctrl[_t].setStyleSheet(pfadef.SS_INCOMPLETE)
            else:
                _tctrl[_t].setEnabled(False)
                _tctrl[_t].setText(f"{pfadef.task_labels[_t]}")
                _tctrl[_t].setStyleSheet("")
        # for i, _t in enumerate(self.data.protocol.task_enabled):
        #     _tctrl[_t].setEnabled(self.data.protocol.calibrated)
        #     if self.data.protocol.calibrated:
        #         if _t in self.data.protocol.task_completed:
        #             _tctrl[_t].setText(f"{pfadef.task_labels[_t]} [C]")
        #             _tctrl[_t].setStyleSheet(pfadef.SS_COMPLETE)
        #         else:
        #             _tctrl[_t].setText(f"{pfadef.task_labels[_t]}")
        #             _tctrl[_t].setStyleSheet(pfadef.SS_INCOMPLETE)
        #     else:
        #         _tctrl[_t].setStyleSheet("")
    
    def _any_mechanism_selected(self):
        """Check if any mechanism is selected.
        """
        return (self.rbWFE.isChecked() or
                self.rbFPS.isChecked() or
                self.rbHOC.isChecked())

    def _get_chosen_mechanism(self):
        """Get the selected mechanism.
        """
        if self.rbWFE.isChecked():
            return "WFE"
        elif self.rbFPS.isChecked():
            return "FPS"
        elif self.rbHOC.isChecked():
            return "HOC"
        else:
            return None
    
    def _reset_mech_selection(self):
        """Reset the mechanism selection.
        """
        self.rbWFE.setChecked(False)
        self.rbFPS.setChecked(False)
        self.rbHOC.setChecked(False)
    
    def _get_chosen_mechanism_event(self):
        """Get the event for the selected mechanism.
        """
        if self.rbWFE.isChecked():
            return Events.WFE_SET
        elif self.rbFPS.isChecked():
            return Events.FPS_SET
        elif self.rbHOC.isChecked():
            return Events.HOC_SET
        else:
            return None
        
    def _display_pluto_data(self):
        # Check if new data is available
        if self.pluto.is_data_available() is False:
            self.textPlutoData.setText("No data available.")
            return
        # New data available. Format and display
        _dispdata = [
            f"Dev Name  : {self.pluto.devname} | {self.pluto.version} ({self.pluto.compliedate})",
            f"Time      : {self.pluto.systime} | {self.pluto.currt:6.3f}s | {self.pluto.packetnumber:06d}",
        ]
        _statusstr = ' | '.join((pdef.get_name(pdef.OutDataType, self.pluto.datatype),
                                 pdef.get_name(pdef.ControlTypes, self.pluto.controltype),
                                 pdef.get_name(pdef.CalibrationStatus, self.pluto.calibration)))
        _dispdata += [
            f"Status    : {_statusstr}",
            f"Error     : {pdef.get_name(pdef.ErrorTypes, self.pluto.error)}",
            f"Limb-Mech : {pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism):<6s} | {pdef.get_name(pdef.LimbType, self.pluto.limb):<6s} | {pdef.get_name(pdef.CalibrationStatus, self.pluto.calibration)}",
            f"Button    : {self.pluto.button}",
            ""
        ]
        _dispdata += [
            "~ SENSOR DATA ~",
            f"Angle     : {self.pluto.angle:-07.2f}deg"
            + (f" [{self.pluto.hocdisp:05.2f}cm]" if self.pluto.calibration == 1 else "")
        ]
        _dispdata += [
            f"Control   : {self.pluto.control:3.1f}",
            f"Target    : {self.pluto.target:3.1f} | Desired  : {self.pluto.desired:3.1f}",
        ]
        # Check if in DIAGNOSTICS mode.
        if pdef.get_name(pdef.OutDataType, self.pluto.datatype) == "DIAGNOSTICS":
            _dispdata += [
                f"Err       : {self.pluto.err:3.1f}",
                f"ErrDiff   : {self.pluto.errdiff:3.1f}",
                f"ErrSum    : {self.pluto.errsum:3.1f}",
            ]
        self.textPlutoData.setText('\n'.join(_dispdata))

    #
    # Device Data Viewer Functions 
    #

    #
    # Main window close event
    # 
    def closeEvent(self, event):
        try:
            self.pluto.set_control_type("NONE")
            self.pluto.close()
        except Exception as e:
            print(f"Error during close: {e}")
        # Accept the close event.
        event.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoFullAssesor("COM13")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())