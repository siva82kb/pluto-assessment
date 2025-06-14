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
import json

from enum import Enum, auto

from qtpluto import QtPluto
# import plutodefs as pdef
# import plutofullassessdef as pfadef
from datetime import datetime as dt

# from PyQt5 import (
#     QtWidgets,)
# from PyQt5.QtCore import (
#     QTimer,)
# from PyQt5.QtWidgets import (
#     QMessageBox,
#     QInputDialog
# )
# from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QAbstractTableModel, Qt, QVariant

# import plutofullassessdef as passdef

# from plutodataviewwindow import PlutoDataViewWindow
# from plutocalibwindow import PlutoCalibrationWindow
# from plutotestwindow import PlutoTestControlWindow
# from plutoapromwindow import PlutoAPRomAssessWindow
# from plutoromwindow import PlutoRomAssessWindow
# from plutopropassesswindow import PlutoPropAssessWindow

# from ui_plutofullassessment import Ui_PlutoFullAssessor

from plutofullassesssdata import PlutoAssessmentData
# from misc import CSVBufferWriter


class Events(Enum):
    SUBJECT_SET = 0
    LIMB_SET = auto()
    #
    # Mechanisms events
    #
    NOMECH_SET = auto()
    WFE_SET = auto()
    FPS_SET = auto()
    HOC_SET = auto()
    WFE_SKIP = auto()
    FPS_SKIP = auto()
    HOC_SKIP = auto()
    #
    # Calibration events
    #
    CALIB_DONE = auto()
    CALIB_NO_DONE = auto()
    #
    # AROM events
    #
    AROM_ASSESS = auto()
    AROM_DONE = auto()
    AROM_NO_DONE = auto()
    AROM_SKIP = auto()
    AROM_REJECT = auto()
    #
    # PROM events
    #
    PROM_ASSESS = auto()
    PROM_DONE = auto()
    PROM_NO_DONE = auto()
    PROM_SKIP = auto()
    PROM_REJECT = auto()
    #
    # APROM Slow events
    #
    APROMSLOW_ASSESS = auto()
    APROMSLOW_DONE = auto()
    APROMSLOW_NO_DONE = auto()
    APROMSLOW_SKIP = auto()
    APROMSLOW_REJECT = auto()
    #
    # APROM Fast events
    #
    APROMFAST_ASSESS = auto()
    APROMFAST_DONE = auto()
    APROMFAST_NO_DONE = auto()
    APROMFAST_SKIP = auto()
    APROMFAST_REJECT = auto()
    #
    # Position hold events
    #
    POSHOLD_ASSESS = auto()
    POSHOLD_DONE = auto()
    POSHOLD_NO_DONE = auto()
    POSHOLD_SKIP = auto()
    POSHOLD_REJECT = auto()
    #
    # Discrete reaching events
    #
    DISCREACH_ASSESS = auto()
    DISCREACH_DONE = auto()
    DISCREACH_NO_DONE = auto()
    DISCREACH_SKIP = auto()
    DISCREACH_REJECT = auto()
    #
    # Proprioception events
    #
    PROP_ASSESS = auto()
    PROP_DONE = auto()
    PROP_NO_DONE = auto()
    PROP_SKIP = auto()
    PROP_REJECT = auto()
    #
    # Force control low events
    FCTRLLOW_ASSESS = auto()
    FCTRLLOW_DONE = auto()
    FCTRLLOW_NO_DONE = auto()
    FCTRLLOW_SKIP = auto()
    FCTRLLOW_REJECT = auto()
    #
    # Force control medium events
    FCTRLMED_ASSESS = auto()
    FCTRLMED_DONE = auto()
    FCTRLMED_NO_DONE = auto()
    FCTRLMED_SKIP = auto()
    FCTRLMED_REJECT = auto()
    #
    # Force control high events
    FCTRLHIGH_ASSESS = auto()
    FCTRLHIGH_DONE = auto()
    FCTRLHIGH_NO_DONE = auto()
    FCTRLHIGH_SKIP = auto()
    FCTRLHIGH_REJECT = auto()

    @classmethod
    def mech_selected_events(cls):
        return [
            Events.WFE_SET,
            Events.FPS_SET,
            Events.HOC_SET,
            Events.NOMECH_SET
        ]
    
    @classmethod
    def mech_skip_events(cls):
        return [
            Events.WFE_SKIP,
            Events.FPS_SKIP,
            Events.HOC_SKIP
        ]
    
    @classmethod
    def task_selected_events(cls):
        return [
            Events.AROM_ASSESS,
            Events.PROM_ASSESS,
            Events.APROMSLOW_ASSESS,
            Events.APROMFAST_ASSESS,
            Events.POSHOLD_ASSESS,
            Events.DISCREACH_ASSESS,
            Events.PROP_ASSESS,
            Events.FCTRLLOW_ASSESS,
            Events.FCTRLMED_ASSESS,
            Events.FCTRLHIGH_ASSESS,
        ]
    
    @classmethod
    def task_skip_events(cls):
        return [
            Events.AROM_SKIP,
            Events.PROM_SKIP,
            Events.APROMSLOW_SKIP,
            Events.APROMFAST_SKIP,
            Events.POSHOLD_SKIP,
            Events.DISCREACH_SKIP,
            Events.PROP_SKIP,
            Events.FCTRLLOW_SKIP,
            Events.FCTRLMED_SKIP,
            Events.FCTRLHIGH_SKIP,
        ]


class States(Enum):
    SUBJ_SELECT = 0
    LIMB_SELECT = auto()
    MECH_SELECT = auto()
    MECH_OR_TASK_SELECT = auto()
    CALIBRATE = auto()
    AROM_ASSESS = auto()
    PROM_ASSESS = auto()
    APROMSLOW_ASSESS = auto()
    APROMFAST_ASSESS = auto()
    POSHOLD_ASSESS = auto()
    DISC_ASSESS = auto()
    PROP_ASSESS = auto()
    FCTRLLOW_ASSESS = auto()
    FCTRLMED_ASSESS = auto()
    FCTRLHIGH_ASSESS = auto()
    TASK_SELECT = auto()
    TASK_DONE = auto()
    MECH_DONE = auto()
    SUBJ_LIMB_DONE = auto()


class PlutoFullAssessmentStateMachine():
    def __init__(self, plutodev: QtPluto, data: PlutoAssessmentData, progconsole):
        self._state = States.SUBJ_SELECT
        self._data: PlutoAssessmentData = data
        self._instruction = ""
        self._protocol = None
        self._pconsole = progconsole
        self._pconsolemsgs = []
        # Indicates if both AROM and PROM have been done for this
        # particular instance of the statemachine.
        self._pluto = plutodev
        self._stateactions = {
            States.SUBJ_SELECT: self._handle_subject_select,
            States.LIMB_SELECT: self._handle_limb_select,
            States.MECH_SELECT: self._handle_mechanism_select,
            States.CALIBRATE: self._handle_calibrate,
            States.AROM_ASSESS: self._handle_arom_assess,
            States.PROM_ASSESS: self._handle_prom_assess,
            States.APROMSLOW_ASSESS: self._handle_apromslow_assess,
            States.APROMFAST_ASSESS: self._handle_apromfast_assess,
            States.POSHOLD_ASSESS: self._handle_poshold_assess,
            States.DISC_ASSESS: self._handle_discreach_assess,
            States.PROP_ASSESS: self._handle_prop_assess,
            States.FCTRLLOW_ASSESS: self._handle_fctrllow_assess,
            States.FCTRLMED_ASSESS: self._handle_fctrlmed_assess,
            States.FCTRLHIGH_ASSESS: self._handle_fctrlhigh_assess,
            States.TASK_SELECT: self._handle_task_select,
            States.TASK_DONE: self._task_done,
            States.MECH_DONE: self._handle_mechanism_done,
            States.SUBJ_LIMB_DONE: self._handle_subject_limb_done,
            States.MECH_OR_TASK_SELECT: self._handle_mechanism_or_task_select,
        }
        # Task to next state dictionary.
        self._task_to_nextstate = {
            "AROM": States.AROM_ASSESS,
            "PROM": States.PROM_ASSESS,
            "APROMSLOW": States.APROMSLOW_ASSESS,
            "APROMFAST": States.APROMFAST_ASSESS,
            "POSHOLD": States.POSHOLD_ASSESS,
            "DISC": States.DISC_ASSESS,
            "PROP": States.PROP_ASSESS,
            "FCTRLLOW": States.FCTRLLOW_ASSESS,
            "FCTRLMED": States.FCTRLMED_ASSESS,
            "FCTRLHIGH": States.FCTRLHIGH_ASSESS,
        }
        # Event to next state dictionary.
        self._event_to_nextstate = {
            Events.AROM_ASSESS: States.AROM_ASSESS,
            Events.PROM_ASSESS: States.PROM_ASSESS,
            Events.APROMSLOW_ASSESS: States.APROMSLOW_ASSESS,
            Events.APROMFAST_ASSESS: States.APROMFAST_ASSESS,
            Events.POSHOLD_ASSESS: States.POSHOLD_ASSESS,
            Events.DISCREACH_ASSESS: States.DISC_ASSESS,
            Events.PROP_ASSESS: States.PROP_ASSESS,
            Events.FCTRLLOW_ASSESS: States.FCTRLLOW_ASSESS,
            Events.FCTRLMED_ASSESS: States.FCTRLMED_ASSESS,
            Events.FCTRLHIGH_ASSESS: States.FCTRLHIGH_ASSESS,
        }
    
    @property
    def state(self):
        return self._state
    
    @property
    def instruction(self):
        return self._instruction
    
    def run_statemachine(self, event, data):
        """Execute the state machine depending on the given even that has occured.
        """
        self._stateactions[self._state](event, data)

    def _handle_subject_select(self, event, data):
        """
        """
        if event == Events.SUBJECT_SET:
            # Set the subject ID.
            self._data.set_subject(subjid=data["subjid"],
                                   subjtype=data["subjtype"],
                                   domlimb=data["domlimb"],
                                   afflimb=data["afflimb"])
            # We need to now select the limb.
            self._state = States.LIMB_SELECT
            self._pconsole.append(self._instruction)
    
    def _handle_limb_select(self, event, data):
        """
        """
        if event == Events.LIMB_SET:
            # Set limb type and limb.
            self._data.set_limb(limb=data["limb"])
            # We need to now select the mechanism.
            self._state = States.MECH_SELECT
            self._pconsole.append(self._instruction)
            # Generated assessment protocol.
            self._data.start_protocol()
            self.log(f"Protocol started.")

    def _handle_mechanism_select(self, event, data):
        """
        """
        # Check if a mechanism is skipped.
        if event in Events.mech_skip_events():
            _event_mech_map = {
                Events.WFE_SKIP: "WFE",
                Events.FPS_SKIP: "FPS",
                Events.HOC_SKIP: "HOC"
            }
            # Set current mechanism.
            self._data.protocol.skip_mechanism(_event_mech_map[event],
                                               session=data["session"],
                                               comment=data["comment"])
            self._data.detailedsummary.skip_mechanism(_event_mech_map[event])
            self.log(f"Mechanism {self._data.protocol.mech} skipped.")
            return
        # Check if a mechanism is selected.
        if event in Events.mech_selected_events():
            _event_mech_map = {
                Events.WFE_SET: "WFE",
                Events.FPS_SET: "FPS",
                Events.HOC_SET: "HOC",
                Events.NOMECH_SET: ""
            }
            if event == Events.NOMECH_SET:
                self._data.protocol.set_mechanism(None)
                self._data.detailedsummary.set_mechanism(None)
                return
            # Set current mechanism.
            print(f"Setting mechanism to {_event_mech_map[event]}")
            self._data.protocol.set_mechanism(_event_mech_map[event])
            self._data.detailedsummary.set_mechanism(_event_mech_map[event])
            # Check if the mechanism is already completed.
            if self._data.protocol.mech in self._data.protocol.mech_completed:
                # Check if the current mechanism has been assessed.
                self._state = States.MECH_OR_TASK_SELECT
            else:
                self._state = States.CALIBRATE
            self.log(f"Mechanism set to {self._data.protocol.mech}.")
        return

    def _handle_calibrate(self, event, data):
        """
        """
        # Check if the calibration is done.
        if event == Events.CALIB_DONE:
            self._data.protocol.set_mechanism_calibrated(data["mech"])
            self.log(f"Mechanism {self._data.protocol.mech} calibrated.")
            # Check if the chosen mechanism has been assessed.
            if self._data.protocol.mech in self._data.protocol.mech_completed:
                self._state = States.MECH_OR_TASK_SELECT
            else:
                # Jump to the next task state.
                # Check if the current mechanism has been assessed.
                self._state = (
                    States.MECH_OR_TASK_SELECT
                    if self._data.protocol.current_mech_completed
                    else States.TASK_SELECT
                )
        elif event == Events.CALIB_NO_DONE:
            # Jump to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Mechanism {self._data.protocol.mech} calibrated.")

    def _handle_arom_assess(self, event, data):
        """
        """
        # Check if AROM is set.
        if event == Events.AROM_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                session=self._data.session,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            _romval = self._data.detailedsummary[self._data.protocol.mech]["tasks"]['AROM'][-1]['rom']
            self.log(f"AROM Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        elif event == Events.AROM_NO_DONE or event == Events.AROM_REJECT:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"AROM not done for {self._data.protocol.mech}.")
    
    def _handle_prom_assess(self, event, data):
        """
        """
        # Check if PROM is et.
        if event == Events.PROM_DONE:
            # Update PROM assessment data.
            self._data.detailedsummary.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            _romval = self._data.detailedsummary[self._data.protocol.mech]["tasks"]['PROM'][-1]['rom']
            self.log(f"PROM Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        # else:
        #     self._state = States.TASK_SELECT
        elif event == Events.PROM_NO_DONE or event == Events.PROM_REJECT:
            # Update PROM assessment data.
            self._data.detailedsummary.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"PROM not done for {self._data.protocol.mech}.")

    def _handle_apromslow_assess(self, event, data):
        """
        """
        # Check if APROM is et.
        if event == Events.APROMSLOW_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            _romval = self._data.detailedsummary[self._data.protocol.mech]["tasks"]['APROMSLOW'][-1]['rom']
            self.log(f"APROMSLOW Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        elif event == Events.APROMSLOW_NO_DONE or event == Events.APROMSLOW_REJECT:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"APROMSLOW not done for {self._data.protocol.mech}.")

    def _handle_apromfast_assess(self, event, data):
        """
        """
        # Check if AROM is et.
        if event == Events.APROMFAST_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            _romval = self._data.detailedsummary[self._data.protocol.mech]["tasks"]['APROMFAST'][-1]['rom']
            self.log(f"APROMFAST Set: [{_romval[0]:+2.2f}, {_romval[1]:+2.2f}]")
        elif event == Events.APROMFAST_NO_DONE or event == Events.APROMFAST_REJECT:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                romval=data["romval"],
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"APROMFAST not done for {self._data.protocol.mech}.")
    
    def _handle_poshold_assess(self, event, data):
        """
        """
        # Check if discrete reaching is done.
        if event == Events.POSHOLD_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                "",
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Position Hold done for {self._data.protocol.mech}.")
        elif event == Events.POSHOLD_NO_DONE or event == Events.POSHOLD_REJECT:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Position Hold not done for {self._data.protocol.mech}.")
    
    def _handle_discreach_assess(self, event, data):
        """
        """
        # Check if discrete reaching is done.
        if event == Events.DISCREACH_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                "",
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Discrete Reaching done for {self._data.protocol.mech}.")
        elif event == Events.DISCREACH_NO_DONE or event == Events.DISCREACH_REJECT:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Discrete Reaching not done for {self._data.protocol.mech}.")

    def _handle_prop_assess(self, event, data):
        """
        """
        # Check if proprioceptive assessment is done.
        if event == Events.PROP_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                "",
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Proprioception done for {self._data.protocol.mech}.")
        elif event == Events.PROP_NO_DONE or event == Events.PROP_REJECT:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Proprioception not done for {self._data.protocol.mech}.")

    def _handle_fctrllow_assess(self, event, data):
        """
        """
        # Check if proprioceptive assessment is done.
        if event == Events.FCTRLLOW_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                "",
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Force Control (Low) done for {self._data.protocol.mech}.")
        elif event == Events.FCTRLLOW_NO_DONE or event == Events.FCTRLLOW_REJECT:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Force Control (Low) not done for {self._data.protocol.mech}.")

    def _handle_fctrlmed_assess(self, event, data):
        """
        """
        # Check if proprioceptive assessment is done.
        if event == Events.FCTRLMED_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                "",
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Force Control (Medium) done for {self._data.protocol.mech}.")
        elif event == Events.FCTRLMED_NO_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Force Control (Medium) not done for {self._data.protocol.mech}.")

    def _handle_fctrlhigh_assess(self, event, data):
        """
        """
        # Check if proprioceptive assessment is done.
        if event == Events.FCTRLHIGH_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Update the protocol data.
            self._data.protocol.update(
                self._data.session,
                self._data.protocol.rawfilename,
                "",
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Force Control (High) done for {self._data.protocol.mech}.")
        elif event == Events.FCTRLHIGH_NO_DONE:
            # Update AROM assessment data.
            self._data.detailedsummary.update(
                session=self._data.session,
                tasktime=self._data.protocol.tasktime,
                rawfile=self._data.protocol.rawfilename,
                summaryfile=self._data.protocol.summaryfilename,
                taskcomment=data["taskcomment"],
                status=data["status"]
            )
            # Jumpy to the next task state.
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
            self.log(f"Force Control (High) not done for {self._data.protocol.mech}.")

    def _handle_task_select(self, event, data):
        """
        """
        if event in Events.task_selected_events():
            self._handle_task_assess_event(event, data)
        elif event in Events.task_skip_events():
            self._handle_task_skip_event(event, data)

    def _task_done(self, event, data):
        """
        """
        pass

    def _handle_mechanism_done(self, event, data):
        """
        """
        pass

    def _handle_subject_limb_done(self, event, data):
        """
        """
        pass

    def _handle_mechanism_or_task_select(self, event, data):
        """
        """
        # Is a mechanism selected?
        if event in Events.mech_selected_events():
            self._handle_mechanism_select(event, data)
        elif event in Events.task_selected_events():
            self._handle_task_select(event, data)
    
    #
    # Supporting functions for the state machine.
    #
    def _handle_task_assess_event(self, event, data):
        # Select the next state
        if event == Events.AROM_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("AROM")
            self._data.detailedsummary.set_task("AROM")
            self.log(f"Task set to AROM.")
        elif event == Events.PROM_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("PROM")
            self._data.detailedsummary.set_task("PROM")
            self.log(f"Task set to PROM.")
        elif event == Events.APROMSLOW_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("APROMSLOW")
            self._data.detailedsummary.set_task("APROMSLOW")
            self.log(f"Task set to APROMSLOW.")
        elif event == Events.APROMFAST_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("APROMFAST")
            self._data.detailedsummary.set_task("APROMFAST")
            self.log(f"Task set to APROMFAST.")
        elif event == Events.POSHOLD_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("POSHOLD")
            self._data.detailedsummary.set_task("POSHOLD")
            self.log(f"Task set to POSHOLD.")
        elif event == Events.DISCREACH_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("DISC")
            self._data.detailedsummary.set_task("DISC")
            self.log(f"Task set to DISC.")
        elif event == Events.PROP_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("PROP")
            self._data.detailedsummary.set_task("PROP")
            self.log(f"Task set to PROP.")
        elif event == Events.FCTRLLOW_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("FCTRLLOW")
            self._data.detailedsummary.set_task("FCTRLLOW")
            self.log(f"Task set to FCTRLLOW.")
        elif event == Events.FCTRLMED_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("FCTRLMED")
            self._data.detailedsummary.set_task("FCTRLMED")
            self.log(f"Task set to FCTRLMED.")
        elif event == Events.FCTRLHIGH_ASSESS:
            self._state = self._event_to_nextstate[event]
            self._data.protocol.set_task("FCTRLHIGH")
            self._data.detailedsummary.set_task("FCTRLHIGH")
            self.log(f"Task set to FCTRLHIGH.")
        elif event is None:
            # Check if the current mechanism has been assessed.
            self._state = (
                States.MECH_OR_TASK_SELECT
                if self._data.protocol.current_mech_completed
                else States.TASK_SELECT
            )
    
    def _handle_task_skip_event(self, event, data):
        # Select the next state
        if event == Events.AROM_SKIP:
            self._data.protocol.skip_task(taskname="AROM",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="AROM",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task AROM skipped.")
        elif event == Events.PROM_SKIP:
            self._data.protocol.skip_task(taskname="PROM",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="PROM",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task PROM skipped.")
        elif event == Events.APROMSLOW_SKIP:
            self._data.protocol.skip_task(taskname="APROMSLOW",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="APROMSLOW",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task APROMSLOW skipped.")
        elif event == Events.APROMFAST_SKIP:
            self._data.protocol.skip_task(taskname="APROMFAST",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="APROMFAST",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task APROMFAST skipped.")
        elif event == Events.POSHOLD_SKIP:
            self._data.protocol.skip_task(taskname="POSHOLD",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="POSHOLD",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task POSHOLD skipped.")
        elif event == Events.DISCREACH_SKIP:
            self._data.protocol.skip_task(taskname="DISC",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="DISC",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task DISC skipped.")
        elif event == Events.PROP_SKIP:
            self._data.protocol.skip_task(taskname="PROP",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="PROP",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task PROP skipped.")
        elif event == Events.FCTRLLOW_SKIP:
            self._data.protocol.skip_task(taskname="FCTRLLOW",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="FCTRLLOW",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task FCTRLLOW skipped.")
        elif event == Events.FCTRLMED_SKIP:
            self._data.protocol.skip_task(taskname="FCTRLMED",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="FCTRLMED",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task FCTRLMED skipped.")
        elif event == Events.FCTRLHIGH_SKIP:
            self._data.protocol.skip_task(taskname="FCTRLHIGH",
                                          session=data["session"],
                                          comment=data["comment"])
            self._data.detailedsummary.skip_task(taskname="FCTRLHIGH",
                                                 session=data["session"],
                                                 comment=data["comment"])
            self.log(f"Task FCTRLHIGH skipped.")
        # Check if the current mechanism has been assessed.
        self._state = (
            States.MECH_OR_TASK_SELECT
            if self._data.protocol.current_mech_completed
            else States.TASK_SELECT
        )
    
    #
    # Protocol console logging
    #
    def log(self, msg):
        """Log the message to the protocol console.
        """
        if len(self._pconsolemsgs) > 100:
            self._pconsolemsgs.pop(0)
        self._pconsolemsgs.append(f"{dt.now().strftime('%m/%d %H:%M:%S'):<15} {msg}")
        self._pconsole.clear()
        self._pconsole.append("\n".join(self._pconsolemsgs))
        self._pconsole.verticalScrollBar().setValue(self._pconsole.verticalScrollBar().maximum())


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df, parent=None):
        super().__init__(parent)
        self._df = df

    def rowCount(self, parent=None):
        return len(self._df.index)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()

        if role == Qt.DisplayRole:
            value = self._df.iloc[index.row(), index.column()]
            return str(value)
        return QVariant()
        
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(self._df.index[section])

        elif role == Qt.FontRole:
            font = QtGui.QFont()
            font.setBold(True)
            return font

        return QVariant()