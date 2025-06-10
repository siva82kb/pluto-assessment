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
from plutoforcecontrolwindow import PlutoForceControlWindow
from myqt import CommentDialog
from ui_plutofullassessment import Ui_PlutoFullAssessor

import plutodefs as pdef
import plutofullassessdef as pfadef
from subjectcreator import SubjectCreator
from subjectselector import SubjectSelector
from plutofullassessstatemachine import PlutoFullAssessmentStateMachine
from plutofullassessstatemachine import Events, States
from plutofullassesssdata import PlutoAssessmentData
from plutoassistpromwindow import PlutoAssistPRomAssessWindow
from plutoposholdwindow import PlutoPositionHoldAssessWindow
from plutodiscreachwindow import PlutoDiscReachAssessWindow
from plutopropassesswindow import PlutoPropAssessWindow
from plutofullassesssdata import DataFrameModel


DEBUG = False


class PlutoFullAssesor(QtWidgets.QMainWindow, Ui_PlutoFullAssessor):
    """Main window of the PLUTO proprioception assessment program.
    """
    
    def __init__(self, port, *args, **kwargs) -> None:
        """View initializer."""
        super(PlutoFullAssesor, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self._flag = False
        self._subjdetails = ""
        self._title = "Pluto Full Assessment"

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
        self._init_timers()

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
        self._attach_guicontrol_callbacks()
        
        # Other windows
        self._init_task_windowvariables()

        # Update UI 
        # A flag to disable the main window when another window is open.
        self._maindisable = False
        self._updatetable = True
        self.update_ui()

        # One time set up
        self._one_time_setup()

    
    @property
    def protocol(self):
        return self.data.protocol
    
    #
    # Controls callback
    #
    def _attach_guicontrol_callbacks(self):
        # Subject
        self.pbCreateSeelectSubject.clicked.connect(self._callback_createselect_subject)
        self.pbSelectSubject.clicked.connect(self._callback_select_subject)
        # Limb
        self.cbLimb.currentIndexChanged.connect(self.update_ui)
        self.pbSetLimb.clicked.connect(self._callback_limb_set)
        # Mechanisms and skip
        self.pbWFE.clicked.connect(self._callback_wfe_assess)
        self.pbWFESkip.clicked.connect(self._callback_wfe_skip)
        self.pbFPS.clicked.connect(self._callback_fps_assess)
        self.pbFPSSkip.clicked.connect(self._callback_fps_skip)
        self.pbHOC.clicked.connect(self._callback_hoc_assess)
        self.pbHOCSkip.clicked.connect(self._callback_hoc_skip)
        # Calibration
        self.pbCalibrate.clicked.connect(self._callback_calibrate)
        # Tasks and skip
        self.pbAROM.clicked.connect(self._callback_assess_arom)
        self.pbAROMSkip.clicked.connect(self._callback_skip_arom)
        self.pbPROM.clicked.connect(self._callback_assess_prom)
        self.pbPROMSkip.clicked.connect(self._callback_skip_prom)
        self.pbAPROMSlow.clicked.connect(self._callback_assess_apromslow)
        self.pbAPROMFast.clicked.connect(self._callback_assess_apromfast)
        self.pbPosHold.clicked.connect(self._callback_poshold_reach)
        self.pbDiscReach.clicked.connect(self._callback_disc_reach)
        self.pbProp.clicked.connect(self._callback_assess_prop)
        # self.pbForceCtrl.clicked.connect(self._callback_assess_fctrl)
        # self.pbStartMechAssessment.clicked.connect(self._callback_start_mech_assess)
        # self.pbSkipMechanismAssessment.clicked.connect(self._callback_skip_mech_assess)
    
    def _callback_createselect_subject(self):
        # Calibration window and open it as a modal window.
        self._subjwnd = SubjectCreator(
            parent=self,
            modal=True,
            onclosecb=self._subjwnd_close_event
        )
        # Disable main controls
        self._maindisable = True
        self._subjwnd.show()
        self._currwndclosed = False
    
    def _callback_select_subject(self):
        # Calibration window and open it as a modal window.
        self._subjwnd = SubjectSelector(
            parent=self,
            modal=True,
            onclosecb=self._subjwnd_close_event
        )
        # Disable main controls
        self._maindisable = True
        self._subjwnd.show()
        self._currwndclosed = False
    
    def _callback_limb_set(self):
        # Check the text of the button.
        if self.pbSetLimb.text() == "Reset Limb":
            return
        # Open dialog to confirm limb selection (Ok or cancel).
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"{self.cbLimb.currentText()} limb selected.\nDo you want to continue?",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply == QMessageBox.Ok:
            self.data.set_limb(self.cbLimb.currentText().lower())

        # Run the state machine.
        self._smachine.run_statemachine(
            Events.LIMB_SET,
            {"limb": self.cbLimb.currentText().lower(),}
        )
        self._title = " | ".join(["Pluto Full Assessment",
                                  self.data.subjid,
                                  self.data.type,
                                  f"Dom: {self.data.domlimb}",
                                  f"Aff: {self.data.afflimb}",
                                  f"Limb: {self.data.limb}",
                                  f"{self.data.session}"])
        # Update UI
        self.update_ui()
    
    def _callback_calibrate(self):
        # Disable main controls
        self._maindisable = True
        # Calibration window and open it as a modal window.
        self._calibwnd = PlutoCalibrationWindow(plutodev=self.pluto,
                                                mechanism=self.protocol.mech,
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
        _reassess = self._reassess_requested("AROM")
        if _reassess is True:
            # Add new task to the protocol.
            self.protocol.add_task(taskname="AROM", mechname=self.protocol.mech)
        elif _reassess is False:
            # If reassessment is not requested, return.
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
                "mechanism": self.protocol.mech,
                "romtype": pfadef.ROMType.ACTIVE,
                "session": self.data.session,
                "ntrials": pfadef.get_task_constants("AROM").NO_OF_TRIALS,
                "rawfile": self.protocol.rawfilename,
                "summaryfile": self.protocol.summaryfilename,
            },
            modal=True,
            onclosecb=self._aromwnd_close_event
        )
        self._romwnd.show()
        self._currwndclosed = False

    def _callback_skip_arom(self):
        # Check if the chosen mechanism is already assessed.
        _comment = CommentDialog(
            label=f"Sure you want to skip AROM? If so give the reason.",
            commentrequired=True,
            optionyesno=True,
        )
        if _comment.exec_() == QtWidgets.QDialog.Accepted:
            _skipcomment = _comment.getText()
            # Run the state machine.
            self._smachine.run_statemachine(
                Events.AROM_SKIP,
                {"comment": _skipcomment, "session": self.data.session}
            )
        self.update_ui()

    def _callback_assess_prom(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        _reassess = self._reassess_requested("PROM")
        if _reassess is True:
            # Add new task to the protocol.
            self.protocol.add_task(taskname="PROM", mechname=self.protocol.mech)
        elif _reassess is False:
            # If reassessment is not requested, return.
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
                "mechanism": self.protocol.mech,
                "romtype": pfadef.ROMType.PASSIVE,
                "session": self.data.session,
                "ntrials": pfadef.get_task_constants("PROM").NO_OF_TRIALS,
                "rawfile": self.protocol.rawfilename,
                "summaryfile": self.protocol.summaryfilename,
                "arom": self.data.detailedsummary.get_arom()
            },
            modal=True,
            onclosecb=self._promwnd_close_event
        )
        self._romwnd.show()
        self._currwndclosed = False
    
    def _callback_skip_prom(self):
        # Check if the chosen mechanism is already assessed.
        _comment = CommentDialog(
            label=f"Sure you want to skip PROM? If so give the reason.",
            commentrequired=True,
            optionyesno=True,
        )
        if _comment.exec_() == QtWidgets.QDialog.Accepted:
            _skipcomment = _comment.getText()
            # Run the state machine.
            self._smachine.run_statemachine(
                Events.PROM_SKIP,
                {"comment": _skipcomment, "session": self.data.session}
            )
        self.update_ui()
    
    def _callback_assess_apromslow(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        _reassess = self._reassess_requested("APROMSLOW")
        if _reassess is True:
            # Add new task to the protocol.
            self.protocol.add_task(taskname="APROMSLOW", mechname=self.protocol.mech)
        elif _reassess is False:
            # If reassessment is not requested, return.
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.APROMSLOW_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._romwnd = PlutoAssistPRomAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.get_task_constants("APROMSLOW").NO_OF_TRIALS,
                "rawfile": self.protocol.rawfilename,
                "summaryfile": self.protocol.summaryfilename,
                "arom": self.data.detailedsummary.get_arom(),
                "duration": pfadef.get_task_constants("APROMSLOW").DURATION,
                "apromtype": "Slow",
            },
            modal=True,
            onclosecb=self._apromslowwnd_close_event
        )
        self._romwnd.show()
        self._currwndclosed = False

    def _callback_assess_apromfast(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        _reassess = self._reassess_requested("APROMFAST")
        if _reassess is True:
            # Add new task to the protocol.
            self.protocol.add_task(taskname="APROMFAST", mechname=self.protocol.mech)
        elif _reassess is False:
            # If reassessment is not requested, return.
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.APROMFAST_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._romwnd = PlutoAssistPRomAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.get_task_constants("APROMFAST").NO_OF_TRIALS,
                "rawfile": self.protocol.rawfilename,
                "summaryfile": self.protocol.summaryfilename,
                "arom": self.data.detailedsummary.get_arom(),
                "duration": pfadef.get_task_constants("APROMFAST").DURATION,
                "apromtype": "Fast",
            },
            modal=True,
            onclosecb=self._apromfastwnd_close_event
        )
        self._romwnd.show()
        self._currwndclosed = False
    
    def _callback_poshold_reach(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        _reassess = self._reassess_requested("POSHOLD")
        if _reassess is True:
            # Add new task to the protocol.
            self.protocol.add_task(taskname="POSHOLD", mechname=self.protocol.mech)
        elif _reassess is False:
            # If reassessment is not requested, return.
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.POSHOLD_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._discwnd = PlutoPositionHoldAssessWindow(
            plutodev=self.pluto,
            assessinfo={
                "subjid": self.data.subjid,
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.get_task_constants("POSHOLD").NO_OF_TRIALS,
                "rawfile": self.protocol.rawfilename,
                "summaryfile": self.protocol.summaryfilename,
                "arom": self.data.detailedsummary.get_arom()
            },
            modal=True,
            onclosecb=self._posholdhwnd_close_event
        )
        self._discwnd.show()
        self._currwndclosed = False
    
    def _callback_disc_reach(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        _reassess = self._reassess_requested("DISC")
        if _reassess is True:
            # Add new task to the protocol.
            self.protocol.add_task(taskname="DISC", mechname=self.protocol.mech)
        elif _reassess is False:
            # If reassessment is not requested, return.
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
                "mechanism": self.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.get_task_constants("DISC").NO_OF_TRIALS,
                "rawfile": self.protocol.rawfilename,
                "summaryfile": self.protocol.summaryfilename,
                "arom": self.data.detailedsummary.get_arom()
            },
            modal=True,
            onclosecb=self._discreachwnd_close_event
        )
        self._discwnd.show()
        self._currwndclosed = False

    def _callback_assess_prop(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        _reassess = self._reassess_requested("PROP")
        if _reassess is True:
            # Add new task to the protocol.
            self.protocol.add_task(taskname="PROP", mechname=self.protocol.mech)
        elif _reassess is False:
            # If reassessment is not requested, return.
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
                "mechanism": self.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.get_task_constants("PROP").NO_OF_TRIALS,
                "rawfile": self.protocol.rawfilename,
                "summaryfile": self.protocol.summaryfilename,
                "arom": self.data.detailedsummary.get_arom(),
                "prom": self.data.detailedsummary["PROM"][self.protocol.mech][-1]["rom"]
            },
            modal=True,
            onclosecb=self._propasswnd_close_event
        )
        self._discwnd.show()
        self._currwndclosed = False

    def _callback_assess_fctrl(self):
        # Check if AROM has already been assessed and needs to be reassessed.
        _reassess = self._reassess_requested("FCTRL")
        if _reassess is True:
            # Add new task to the protocol.
            self.protocol.add_task(taskname="FCTRL", mechname=self.protocol.mech)
        elif _reassess is False:
            # If reassessment is not requested, return.
            return
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.FCTRL_ASSESS,
            None
        )
        # Disable main controls
        self._maindisable = True
        self._discwnd = PlutoForceControlWindow(
            plutodev=self.pluto,
            assessinfo={
                "subjid": self.data.subjid,
                "type": self.data.type,
                "limb": self.data.limb,
                "mechanism": self.protocol.mech,
                "session": self.data.session,
                "ntrials": pfadef.get_task_constants("FCTRL").NO_OF_TRIALS,
                "rawfile": self.protocol.rawfilename,
                "summaryfile": self.protocol.summaryfilename,
                "arom": self.data.detailedsummary.get_arom()
            },
            modal=True,
            onclosecb=self._fctrlasswnd_close_event
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
    
    def _callback_wfe_assess(self):
        self._callback_start_mech_assess("WFE")
        self.update_ui()
    
    def _callback_fps_assess(self):
        self._callback_start_mech_assess("FPS")
        self.update_ui()
    
    def _callback_hoc_assess(self):
        self._callback_start_mech_assess("HOC")
        self.update_ui()
    
    def _callback_wfe_skip(self):
        self._callback_skip_mech_assess("WFE")
        self.update_ui()
    
    def _callback_fps_skip(self):
        self._callback_skip_mech_assess("FPS")
        self.update_ui()
    
    def _callback_hoc_skip(self):
        self._callback_skip_mech_assess("HOC")
        self.update_ui()
    
    def _callback_start_mech_assess(self, mech_chosen):
        # Check if the chosen mechanism is already assessed.
        _mechstatus = self.protocol.get_mech_status(mech_chosen)
        print(mech_chosen, _mechstatus)
        if (_mechstatus == pfadef.AssessStatus.COMPLETE 
            or _mechstatus == pfadef.AssessStatus.PARTIALCOMPLETE):
            # Ask if the user wants to continue with this mechanism.
            reply = QMessageBox.question(
                self,
                "Confirm",
                f"Mechanism [{mech_chosen}] already assessed.\nDo you want to continue?",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                # Cancel the radio button selection.
                self._reset_mech_selection()
                # Get the appropriate event.
                self._smachine.run_statemachine(
                    self._get_chosen_mechanism_event(),
                    {}
                )
                self.update_ui()
                return
        # Message box to inform the user that the mechanism is selected.
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Start {mech_chosen} assessment?\n\n",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply == QMessageBox.Cancel:
            # Cancel the radio button selection.
            self._reset_mech_selection()
        # Run the state machine.
        # Get the appropriate event.
        _mechevent = {"WFE": Events.WFE_SET,
                      "FPS": Events.FPS_SET,
                      "HOC": Events.HOC_SET}
        self._smachine.run_statemachine(
            _mechevent[mech_chosen],
            {}
        )
        self._flag = True
        self.update_ui()
    
    def _callback_skip_mech_assess(self, mech_chosen):
        # Check if the chosen mechanism is already assessed.
        _comment = CommentDialog(
            label="Sure you want to skip? If so give the reason.",
            commentrequired=True,
            optionyesno=True,
        )
        if _comment.exec_() == QtWidgets.QDialog.Accepted:
            _skipcomment = _comment.getText()
            # Run the state machine.
            # Get the appropriate event.
            _mechevent = {"WFE": Events.WFE_SKIP,
                          "FPS": Events.FPS_SKIP,
                          "HOC": Events.HOC_SKIP}
            
            self._smachine.run_statemachine(
                _mechevent[mech_chosen],
                {"comment": _skipcomment, "session": self.data.session}
            )
        self.update_ui()

        # if self.protocol.is_mechanism_assessed(_mechchosen):
        #     # Ask if the user wants to continue with this mechanism.
        #     reply = QMessageBox.question(
        #         self,
        #         "Confirm",
        #         f"Mechanism [{_mechchosen}] already assessed.\nDo you want to continue?",
        #         QMessageBox.Ok | QMessageBox.Cancel
        #     )
        #     if reply == QMessageBox.Cancel:
        #         # Cancel the radio button selection.
        #         self._reset_mech_selection()
        #         # Get the appropriate event.
        #         self._smachine.run_statemachine(
        #             self._get_chosen_mechanism_event(),
        #             {}
        #         )
        #         print(self.data.mechanism)
        #         self.update_ui()
        #         return
        # # Message box to inform the user that the mechanism is selected.
        # reply = QMessageBox.question(
        #     self,
        #     "Confirm",
        #     f"Start {_mechchosen} assessment?\n\n",
        #     QMessageBox.Ok | QMessageBox.Cancel
        # )
        # if reply == QMessageBox.Cancel:
        #     # Cancel the radio button selection.
        #     self._reset_mech_selection()
        # # Run the state machine.
        # # Get the appropriate event.
        # self._smachine.run_statemachine(
        #     self._get_chosen_mechanism_event(),
        #     {}
        # )
        # self.update_ui()
    
    # 
    # Timer callbacks
    #
    def _init_timers(self):
        # Status timer
        self.statustimer = QTimer()
        self.statustimer.timeout.connect(self._callback_status_timer)
        self.statustimer.start(1000)
        self.apptime = 0
        # Display timer
        self.displaytimer = QTimer()
        self.displaytimer.timeout.connect(self._callback_display_timer)
        self.displaytimer.start(pfadef.DISPLAY_INTERVAL)
        # Heartbeat timer
        self.heartbeattimer = QTimer()
        self.heartbeattimer.timeout.connect(lambda: self.pluto.send_heartbeat())
        self.heartbeattimer.start(250)
    
    def _callback_status_timer(self):
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
    
    def _callback_display_timer(self):
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
    # Signal callbacks
    #
    def _callback_newdata(self):
        """Update the UI of the appropriate window.
        """
        # Update data viewer window.
        if np.random.rand() < 0.05:
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
    def _subjwnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._subjwnd = None
            return
        # Run the state machine.
        if data:
            self._smachine.run_statemachine(
                Events.SUBJECT_SET,  
                data
            )
            self._subjdetails = self._get_subject_details()
            self._title = " | ".join(["Pluto Full Assessment",
                                      self.data.subjid,
                                      self.data.type,
                                      f"Dom: {self.data.domlimb}",
                                      f"Aff: {self.data.afflimb}"])
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _calibwnd_close_event(self, data=None):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._calibwnd = None
            return
        # Window not closed.
        # Reenable main controls
        self._maindisable = False
        # Check of the calibration was successful.
        if (pdef.get_name(pdef.Mehcanisms, self.pluto.mechanism) == self.protocol.mech
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
            data
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
            data
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _apromslowwnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._romwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.APROMSLOW_DONE if data["done"] else Events.APROMSLOW_NO_DONE,
            data
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _apromfastwnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._romwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.APROMFAST_DONE if data["done"] else Events.APROMFAST_NO_DONE,
            data
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _posholdhwnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._discwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.POSHOLD_DONE if data["done"] else Events.POSHOLD_NO_DONE,
            data
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
            data
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
            data
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()
    
    def _fctrlasswnd_close_event(self, data):
        # Check if the window is already closed.
        if self._currwndclosed is True:
            self._discwnd = None
            return
        # Window not closed.
        # Run the state machine.
        self._smachine.run_statemachine(
            Events.FCTRL_DONE if data["done"] else Events.FCTRL_NO_DONE,
            data
        )
        # Reenable main controls
        self._maindisable = False
        # Update the Table.
        self._updatetable = True
        # Set the window closed flag.
        self._currwndclosed = True
        self.update_ui()

    #
    # UI Update function
    #
    def update_ui(self):        
        self.setWindowTitle(self._title)
        # Select subject
        self.pbCreateSeelectSubject.setEnabled(self._maindisable is False
                                               and self._smachine.state == States.SUBJ_SELECT)
        self.pbSelectSubject.setEnabled(self._maindisable is False
                                        and self._smachine.state == States.SUBJ_SELECT)
        
        # Limb selection
        _lmbflag = self._maindisable is False and self._smachine.state == States.LIMB_SELECT
        self.lblSubjDetails.setText(self._subjdetails)
        self.lblLimb.setEnabled(_lmbflag)
        self.cbLimb.setEnabled(_lmbflag)
        
        # Set limb button
        self.pbSetLimb.setEnabled(self.cbLimb.currentText() != "")

        # Update the table.
        if self.protocol and self.protocol.df is not None and self._updatetable: 
            self.tableProtocolProgress.setModel(DataFrameModel(self.protocol.df))
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
        self.pbSetLimb.setEnabled(self.cbLimb.currentText() != ""
                                  and self._smachine.state == States.LIMB_SELECT)
        self.gbMechanisms.setEnabled(_mechflag)
        
        # Enable the appropriate mechanisms.
        self._update_mech_controls()

        # Check if any mechanism is selected to enable the mechanism assessment start button.
        # self.pbStartMechAssessment.setEnabled(self._any_mechanism_selected())
        # self.pbSkipMechanismAssessment.setEnabled(self._any_incomplete_mechanism_selected())

        # Enable the calibration button.
        self.pbCalibrate.setEnabled(self._maindisable is False 
                                    and self.protocol is not None 
                                    and self.protocol.mech is not None)
        if self.pbCalibrate.isEnabled():
            self.pbCalibrate.setStyleSheet(
                pfadef.STATUS_STYLESHEET[pfadef.AssessStatus.COMPLETE]
                if self.protocol.calibrated 
                else pfadef.STATUS_STYLESHEET[pfadef.AssessStatus.INCOMPLETE]
            )
        else:
            self.pbCalibrate.setStyleSheet("")

        # Enable the task buttons.
        self._update_task_controls()
        
        # Update session information.
        self.lblSessionInfo.setText(self._get_session_info()) 

    #
    # Supporting functions
    #
    def _get_subject_details(self):
        """Get the subject details string.
        """
        _text = f"{self.data.subjid}"
        _text += f" | Dom: {self.data.domlimb:<6}"
        if self.data.type == "stroke":
            _text += f" | Aff: {self.data.afflimb:<6}"
        return _text
    
    def _one_time_setup(self):
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(10)
        self.pbWFE.setFont(font)
        self.pbFPS.setFont(font)
        self.pbHOC.setFont(font)
        self.pbWFESkip.setFont(font)
        self.pbFPSSkip.setFont(font)
        self.pbHOCSkip.setFont(font)
    
    def _init_task_windowvariables(self):
        self._devdatawnd = None
        self._calibwnd = None
        self._testdevwnd = None
        self._romwnd = None
        self._discwnd = None
        self._propwnd = None
        self._currwndclosed = True
        self._wnddata = {}
    
    def _get_session_info(self):
        _str = [
            f"{'' if self.data.session is None else self.data.session:<20}",
            f"{'' if self.data.subjid is None else self.data.subjid:<8}",
            f"{self.data.type if self.data.type is not None else '':<8}",
            f"{self.data.limb if self.data.limb is not None else '':<8}"
        ]
        return ":".join(_str)
    
    def _reassess_requested(self, task):
        """
        """
        if self.protocol.index is not None and task not in self.protocol.task_enabled[:-1]:
            return None
        # Ask the experimenter if this assessment is to be repeated.
        reply = QMessageBox.question(
            self,
            "Reassessment Confirmation",
            f"{task} has been assessed before.\nDo you want to reassess?",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        return reply == QMessageBox.Ok

    def _update_mech_controls(self):
        if self.protocol is None: return
        # Update the text of the radio buttons.
        _mctrl = {
            "WFE": [self.pbWFE, self.pbWFESkip],
            "FPS": [self.pbFPS, self.pbFPSSkip],
            "HOC": [self.pbHOC, self.pbHOCSkip]
        }
        # Update complete/incomplete status of the mechanisms.
        for i, _m in enumerate(self.protocol.mech_enabled):
            _mctrl[_m][0].setEnabled(True)
            _mechstatus = self.protocol.get_mech_status(_m)
            _mctrl[_m][0].setStyleSheet(pfadef.STATUS_STYLESHEET[_mechstatus])
            _mctrl[_m][0].setText(f"{pfadef.MECH_LABELS[_m]} {pfadef.STATUS_TEXT[_mechstatus]}")
            # Update the skip buttons
            _mctrl[_m][1].setEnabled(_mechstatus == pfadef.AssessStatus.INCOMPLETE)

    def _update_task_controls(self):
        if self.protocol is None: return 
        _tctrl = {
            "AROM": [self.pbAROM, self.pbAROMSkip],
            "PROM": [self.pbPROM, self.pbPROMSkip],
            "APROMSLOW": [self.pbAPROMSlow, self.pbAPROMSlowSkip],
            "APROMFAST": [self.pbAPROMFast, self.pbAPROMFastSkip],
            "POSHOLD": [self.pbPosHold, self.pbPosHoldSkip],
            "DISC": [self.pbDiscReach, self.pbDiscReachSkip],
            "PROP": [self.pbProp, self.pbPropSkip],
            "FCTRLLOW": [self.pbForceCtrlLow, self.pbForceCtrlLowSkip],
            "FCTRLMED": [self.pbForceCtrlMed, self.pbForceCtrlMedSkip],
            "FCTRLHIGH": [self.pbForceCtrlHigh, self.pbForceCtrlHighSkip],
        }
        # Go through all tasks for the mechanism and enable/disable them appropriately.
        for i, _t in enumerate(pfadef.ALLTASKS):
            _taskstatus = self.protocol.get_task_status(_t)
            if self.protocol.calibrated and _t == self.protocol.task_enabled:
                _tctrl[_t][0].setEnabled(_taskstatus == pfadef.AssessStatus.INCOMPLETE)
                _tctrl[_t][0].setStyleSheet(pfadef.STATUS_STYLESHEET[_taskstatus])
                _tctrl[_t][0].setText(f"{pfadef.TASK_LABELS[_t]}{pfadef.STATUS_TEXT[_taskstatus]}")
                _tctrl[_t][1].setEnabled(_taskstatus == pfadef.AssessStatus.INCOMPLETE)
            else:
                _tctrl[_t][0].setEnabled(False)
                _tctrl[_t][0].setStyleSheet(
                    pfadef.STATUS_STYLESHEET[None] 
                    if _taskstatus is pfadef.AssessStatus.INCOMPLETE
                    else pfadef.STATUS_STYLESHEET[_taskstatus]
                )
                _tctrl[_t][0].setText(
                    f"{pfadef.TASK_LABELS[_t]}{pfadef.STATUS_TEXT[None]}"
                    if _taskstatus is pfadef.AssessStatus.INCOMPLETE
                    else f"{pfadef.TASK_LABELS[_t]}{pfadef.STATUS_TEXT[_taskstatus]}"
                )
                _tctrl[_t][1].setEnabled(False)
    
    def _any_mechanism_selected(self):
        """Check if any mechanism is selected.
        """
        return (self.rbWFE.isChecked() or
                self.rbFPS.isChecked() or
                self.rbHOC.isChecked())
    
    def _any_incomplete_mechanism_selected(self):
        """Check if any incomplete mechanism is selected.
        """
        if self.protocol is None: return False
        _wfe_incomplete = self.protocol.get_mech_status("WFE") == pfadef.AssessStatus.INCOMPLETE
        _fps_incomplete = self.protocol.get_mech_status("FPS") == pfadef.AssessStatus.INCOMPLETE
        _hoc_incomplete = self.protocol.get_mech_status("HOC") == pfadef.AssessStatus.INCOMPLETE
        return ((self.rbWFE.isChecked() and _wfe_incomplete) or
                (self.rbFPS.isChecked() and _fps_incomplete) or
                (self.rbHOC.isChecked() and _hoc_incomplete))

    # def _get_chosen_mechanism(self):
    #     """Get the selected mechanism.
    #     """
    #     if self.rbWFE.isChecked():
    #         return "WFE"
    #     elif self.rbFPS.isChecked():
    #         return "FPS"
    #     elif self.rbHOC.isChecked():
    #         return "HOC"
    #     else:
    #         return None
    
    def _reset_mech_selection(self):
        """Reset the mechanism selection.
        """
        for button in self.mechButtonGroup.buttons():
            self.mechButtonGroup.removeButton(button)
            button.setChecked(False)
            self.mechButtonGroup.addButton(button)
    
    # def _get_chosen_mechanism_set_event(self, mechchosen):
    #     """Get the event for the selected mechanism.
    #     """
    #     if mechchosen == WFE:
    #         return Events.WFE_SET
    #     elif self.rbFPS.isChecked():
    #         return Events.FPS_SET
    #     elif self.rbHOC.isChecked():
    #         return Events.HOC_SET
    #     else:
    #         return Events.NOMECH_SET

    def _get_chosen_mechanism_skip_event(self):
        """Get the event for skipping the selected mechanism.
        """
        if self.rbWFE.isChecked():
            return Events.WFE_SKIP
        elif self.rbFPS.isChecked():
            return Events.FPS_SKIP
        elif self.rbHOC.isChecked():
            return Events.HOC_SKIP
        else:
            return None

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