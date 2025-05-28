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
from plutofullassessstatemachine import PlutoFullAssessEvents, PlutoFullAssessStates
from plutofullassesssdata import PlutoAssessmentData
from plutofullassesssdata import PlutoAssessmentProtocolData
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
            self._smachine.run_statemachine(PlutoFullAssessEvents.SUBJECT_SET, 
                                            {"subjid": "1234"})
            _data = {"type": "Stroke", "limb": "Right"}
            self._smachine.run_statemachine(PlutoFullAssessEvents.TYPE_LIMB_SET,
                                            _data)
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
                PlutoFullAssessEvents.SUBJECT_SET,  
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
            PlutoFullAssessEvents.TYPE_LIMB_SET,
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
            PlutoFullAssessEvents.AROM_ASSESS,
            PlutoFullAssessEvents.AROM_ASSESS
        )
        # Update UI
        self.update_ui()
        # Disable main controls
        self._maindisable = True
        self._romwnd = PlutoAPRomAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "mechanism": self.data.protocol.mech,
                "romtype": "Active",
                "session": self.data.session,
                "ntrials": pfadef.protocol["AROM"]["N"],
                "rawfile": self.data.protocol.rawfilename,
                "summaryfile": self.data.protocol.summaryfilename,
            },
            modal=True,
            onclosecb=self._aromwnd_close_event
        )
        # Attach to the aromset and promset events.
        # self._romwnd.closeEvent = self._aromwnd_close_event
        self._romwnd.show()
        self._currwndclosed = False

    def _callback_assess_prom(self):
        # Run the state machine.
        self._smachine.run_statemachine(
            PlutoFullAssessEvents.PROM_ASSESS,
            PlutoFullAssessEvents.PROM_ASSESS
        )
        # Disable main controls
        self._maindisable = True
        self._romwnd = PlutoAPRomAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "mechanism": self.data.protocol.mech,
                "romtype": "Passive",
                "session": self.data.session,
                "ntrials": pfadef.protocol["AROM"]["N"],
                "rawfile": self.data.protocol.rawfilename,
                "summaryfile": self.data.protocol.summaryfilename,
                "arom": self.data.romsumry["AROM"][self.data.protocol.mech][-1]["rom"]
            },
            modal=True
        )
        # Attach to the aromset and promset events.
        self._romwnd.closeEvent = self._promwnd_close_event
        self._romwnd.show()

    def _callback_assess_aprom(self):
        # # Disable main controls
        # self._maindisable = True
        # self._romwnd = PlutoRomAssessWindow(plutodev=self.pluto,
        #                                     mechanism="HOC",
        #                                     modal=True)
        # # Attach to the aromset and promset events.
        # self._romwnd.aromset.connect(self._callback_aromset)
        # self._romwnd.promset.connect(self._callback_promset)
        # self._romwnd.closeEvent = self._romwnd_close_event
        # self._romwnd.show()
        pass

    def _callback_assess_prop(self):
        # Disable main controls
        self._maindisable = True
        # Now create the folder for saving all the data.
        self._create_session_folder()
        # Open the proprioception assessment window.
        self._propwnd = PlutoPropAssessWindow(
            plutodev=self.pluto,
            subjtype=self._subjdetails["type"],
            limb=self._subjdetails["limb"],
            griptype=self._subjdetails["grip"],
            arom=self._romdata['AROM'],
            prom=self._romdata['PROM'], 
            outdir=self._datadir.as_posix(),
            dataviewer=False
        )
        # Attach events
        self._propwnd.closeEvent = self._propwnd_close_event
        self._propwnd.show()

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
            print(self._smachine.state)
            self._smachine.run_statemachine(
                PlutoFullAssessEvents.CALIBRATED,
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
            PlutoFullAssessEvents.AROM_SET,
            {"romval": data}
        )
        # Reenable main controls
        self._maindisable = False
         # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _promwnd_close_event(self, data):
        # Update the protocol data.
        self.data.protocol.update(
            self.data.session,
            self.data.protocol.rawfilename,
            self.data.protocol.summaryfilename
        )
        # Update AROM assessment data.
        self.data.romsumry.update(
            romval=self._romwnd.data.rom,
            session=self.data.session,
            tasktime=self.data.protocol.tasktime,
            rawfile=self.data.protocol.rawfilename,
            summaryfile=self.data.protocol.summaryfilename
        )
        # Update the Table.
        self._updatetable = True
        
        #
        self._romwnd.close()
        self._romwnd = None
        self._wndui = None
        # Reenable main controls
        self._maindisable = False

    def _propwnd_close_event(self, data):
        print("Proprioception assessment window closed.")
        # Set device to no control.
        self.pluto.set_control_type("NONE")
        # Reset variables
        self._propwnd.close()
        self._propwnd.deleteLater()
        self._propwnd = None
        # Reenable main controls
        self._maindisable = False

    #
    # UI Update function
    #
    def update_ui(self):        
        # Select subject
        self.pbSubject.setEnabled(self._maindisable is False and self._smachine.state == PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT)
        
        # Limb selection
        _lmbflag = self._maindisable is False and self._smachine.state == PlutoFullAssessStates.WAIT_FOR_LIMB_SELECT
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
        _mechflag = self._maindisable is False and self._smachine.state == PlutoFullAssessStates.WAIT_FOR_MECHANISM_SELECT
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
        
        # if self._smachine.state == PlutoFullAssessStates.WAIT_FOR_SUBJECT_SELECT:
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
        for i, _m in enumerate(self.data.protocol.mech_enabled):
            _mctrl[_m].setEnabled(True)
            _mctrl[_m].setText(f"{pfadef.mech_labels[_m]} {'[C]' if i < len(self.data.protocol.mech_enabled) - 1 else ''}")
            _mctrl[_m].setStyleSheet(
                pfadef.SS_COMPLETE if i < len(self.data.protocol.mech_enabled) - 1 
                else pfadef.SS_INCOMPLETE
            )
        
    def _update_task_controls(self):
        _tctrl = {
            "AROM": self.pbAROM,
            "PROM": self.pbPROM,
            "APROM": self.pbAPROM,
            "DISC": self.pbDiscReach,
            "PROP": self.pbProp,
            "FCTRL": self.pbForceCtrl,
        }
        for i, _t in enumerate(self.data.protocol.task_enabled):
            _tctrl[_t].setEnabled(self.data.protocol.calibrated)
            if self.data.protocol.calibrated:
                _tctrl[_t].setStyleSheet(
                    pfadef.SS_COMPLETE if i < len(self.data.protocol.task_enabled) - 1 
                    else pfadef.SS_INCOMPLETE
                )
            else:
                _tctrl[_t].setStyleSheet("")
    
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
            return PlutoFullAssessEvents.WFE_MECHANISM_SET
        elif self.rbFPS.isChecked():
            return PlutoFullAssessEvents.FPS_MECHANISM_SET
        elif self.rbHOC.isChecked():
            return PlutoFullAssessEvents.HOC_MECHANISM_SET
        else:
            return None
        
    def _display_pluto_data(self):
        # Check if new data is available
        if self.pluto.is_data_available() is False:
            self.textPlutoData.setText("No data available.")
            return
        # New data available. Format and display
        _dispdata = [
            f"Sys Time: {self.pluto.systime}",
            f"Dev Info: {self.pluto.devname} | Ver: {self.pluto.version} [{self.pluto.compliedate}]",
            f"Dev Time: {self.pluto.currt:6.3f}s | Pack No : {self.pluto.packetnumber:06d}",
        ]
        _statusstr = ' | '.join((pdef.get_name(pdef.OutDataType, self.pluto.datatype),
                                 f"Ctrl Type: {pdef.get_name(pdef.ControlType, self.pluto.controltype)}",
                                 f"Err: {pdef.get_name(pdef.ErrorTypes, self.pluto.error)}"))
        _mechstr = ' | '.join((f"{pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism):<6s}",
                               pdef.get_name(pdef.CalibrationStatus, self.pluto.calibration),
                               "Actuated" if self.pluto.actuated else "Unactuated",
                               f"Button: {self.pluto.button}"))
        _dispdata += [
            f"Status  : {_statusstr}",
            f"Mech    : {_mechstr}",
            # f"Actd    : {self.pluto.actuated:<6d} | Button  : {self.pluto.button}",
            ""
        ]
        _dispdata += [
            "~ SENSOR DATA ~",
            f"Angle   : {self.pluto.angle:-07.2f}deg"
            + (f" [{self.pluto.hocdisp:05.2f}cm]" if self.pluto.calibration == 1 else "")
        ]
        _dispdata += [
            f"Control : {self.pluto.control:3.1f}",
            f"Target  : {self.pluto.target:3.1f}",
        ]
        # Check if in DIAGNOSTICS mode.
        if pdef.get_name(pdef.OutDataType, self.pluto.datatype) == "DIAGNOSTICS":
            _dispdata += [
                f"Err     : {self.pluto.err:3.1f}",
                f"ErrDiff : {self.pluto.errdiff:3.1f}",
                f"ErrSum  : {self.pluto.errsum:3.1f}",
            ]
        self.textPlutoData.setText('\n'.join(_dispdata))

    #
    # Device Data Viewer Functions 
    #
    # def _open_devdata_viewer(self):
    #     self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
    #                                            pos=(50, 400))
    #     self._devdatawnd.show()

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
    mywin = PlutoFullAssesor("COM12")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())