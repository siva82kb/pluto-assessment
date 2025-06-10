"""
Module for handling the operation of the PLUTO calibration window.

Author: Sivakumar Balasubramanian
Date: 02 August 2024
Email: siva82kb@gmail.com
"""


import sys
import pandas as pd
import os
from datetime import datetime as dt

from PyQt5 import (
    QtCore,
    QtWidgets,)
from PyQt5.QtCore import QTimer
from enum import Enum

from ui_subjectcreator import Ui_PlutoSubjectCreatorWindow
import plutofullassessdef as pfadef


#
# Class to handle the subjects list file.
#
class SubjectsListFile:

    HEADER = ["subjid", "subjtype", "domlimb", "afflimb", "createdat"]

    def __init__(self, filename=pfadef.SUBJLIST_FILE):
        self.filename = filename
        # Read if the file exists, else create the file.
        if not os.path.exists(self.filename):
            self.subjlist: pd.DataFrame = pd.DataFrame(columns=self.HEADER)
            # Write to the file.
            self.subjlist.to_csv(self.filename, index=False)
        else:
            self.subjlist: pd.DataFrame = pd.read_csv(self.filename, dtype=str)
    
    def subject_exists(self, subjid):
        """
        Check if a subject exists in the subjects list.
        
        Args:
            subject_id (str): The ID of the subject to check.
        
        Returns:
            bool: True if the subject exists, False otherwise.
        """
        return subjid in self.subjlist['subjid'].values
    
    def add_subject(self, subjinfo: dict):
        if not self.subject_exists(subjinfo['subjid']):
            self.subjlist = pd.concat([self.subjlist, pd.DataFrame([subjinfo])],
                                      ignore_index=True)
            self.subjlist.to_csv(self.filename, index=False)
    
    def get_subject_info(self, subjid: str) -> dict:
        """
        Get the subject information for a given subject ID.
        
        Args:
            subjid (str): The ID of the subject.
        
        Returns:
            dict: The subject information if found, else an empty dict.
        """
        if self.subject_exists(subjid):
            return self.subjlist[self.subjlist['subjid'] == subjid].iloc[0].to_dict()
        return {}


class SubjectCreator(QtWidgets.QMainWindow):
    """
    Class for handling the creation of a new subject.
    """
    def __init__(self, parent=None, modal=False, onclosecb=None):
        """
        Constructor for the SubjectCreator class.
        """
        super(SubjectCreator, self).__init__(parent)
        self.ui = Ui_PlutoSubjectCreatorWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        self.subjlistfile: SubjectsListFile = SubjectsListFile()
        self.newsubject = {}

        # Attach callbacks.
        # Textbox looses focus after text entry.
        self.ui.textSubjID.editingFinished.connect(self._callback_subjid_changed)
        self.ui.cbSubjType.currentIndexChanged.connect(self.update_ui)
        self.ui.cbDomLimb.currentIndexChanged.connect(self.update_ui)
        self.ui.cbAffLimb.currentIndexChanged.connect(self.update_ui)
        self.ui.pbCreate.clicked.connect(self._callback_create_subject)
        self.ui.pbCancel.clicked.connect(self.close)

        # Update UI.
        self.update_ui()
        
        # Set the callback when the window is closed.
        self.on_close_callback = onclosecb

    #
    # Update UI
    #
    def update_ui(self):
        # Everything is disabled by if there is not subejct ID
        _subjidflag = self.ui.textSubjID.text().strip() != ""
        self.ui.cbSubjType.setEnabled(_subjidflag)
        self.ui.cbDomLimb.setEnabled(_subjidflag)
        self.ui.cbAffLimb.setEnabled(_subjidflag)
        # Affect limb is enabled only for stroke subjects
        _strokeflag = self.ui.cbSubjType.currentText().lower() == "stroke"
        self.ui.cbAffLimb.setEnabled(_strokeflag and _subjidflag)
        # Create button is enabled only if all fields are filled
        _createflag = (
            _subjidflag and
            self.ui.cbSubjType.currentText() != "" and
            self.ui.cbDomLimb.currentText() != "" and
            (not _strokeflag or self.ui.cbAffLimb.currentText() != "")
        )

    #
    # UI Callbacks
    #
    def _callback_subjid_changed(self):
        if self.subjlistfile.subject_exists(self.ui.textSubjID.text()):
            QtWidgets.QMessageBox.warning(
                self, "Subject Exists",
                f"Subject ID '{self.ui.textSubjID.text()}' already exists in the list."
            )
            self.ui.textSubjID.setText("")  # Clear the text box
        self.update_ui()
    
    def _callback_create_subject(self):
        """
        Callback for creating a new subject.
        """
        # Get the subject ID
        subjid = self.ui.textSubjID.text().strip().lower()
        if not subjid:
            QtWidgets.QMessageBox.warning(self, "Invalid Subject ID", "Subject ID cannot be empty.")
            return
        
        # Create the subject data
        subjtype = self.ui.cbSubjType.currentText().lower()
        domlimb = self.ui.cbDomLimb.currentText().lower()
        afflimb = self.ui.cbAffLimb.currentText().lower() if subjtype == "stroke" else ""
        
        # Add to the subjects list
        self.newsubject = {
            "subjid": subjid,
            "subjtype": subjtype,
            "domlimb": domlimb,
            "afflimb": afflimb,
            "createdat": dt.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Append to the DataFrame and save
        self.subjlistfile.add_subject(self.newsubject)
        QtWidgets.QMessageBox.information(self, "Subject Created", f"Subject '{subjid}' created successfully.")
        
        # Close the window
        self._createflag = False
        self.close()

    #
    # Close event
    #
    def closeEvent(self, event):
        # Run the callback
        if self.on_close_callback:
            self.on_close_callback(data=self.newsubject)
        return super().closeEvent(event)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    screate = SubjectCreator(onclosecb=lambda data: print(data))
    screate.show()
    sys.exit(app.exec_())
