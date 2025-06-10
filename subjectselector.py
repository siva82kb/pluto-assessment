"""
Module for handling the operation of the subject selection window.

Author: Sivakumar Balasubramanian
Date: 10 June 2025
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

from ui_subjectselector import Ui_PlutoSubjectSelectorWindow
import plutofullassessdef as pfadef
from subjectcreator import SubjectsListFile


class SubjectSelector(QtWidgets.QMainWindow):
    """
    Class for handling the creation of a new subject.
    """
    def __init__(self, parent=None, modal=False, onclosecb=None):
        """
        Constructor for the SubjectSelector class.
        """
        super(SubjectSelector, self).__init__(parent)
        self.ui = Ui_PlutoSubjectSelectorWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.subjlistfile: SubjectsListFile = SubjectsListFile()

        # Populate subjects list.
        self.ui.cbSubjID.clear()
        self.ui.cbSubjID.addItems(
            [""] + self.subjlistfile.subjlist['subjid'].tolist()
        )
        # Attach callbacks.
        # Textbox looses focus after text entry.
        self.ui.cbSubjID.currentIndexChanged.connect(self.update_ui)
        self.ui.pbSelect.clicked.connect(self.close)

        # Update UI.
        self.update_ui()
        
        # Set the callback when the window is closed.
        self.on_close_callback = onclosecb

    #
    # Update UI
    #
    def update_ui(self):
        self.ui.pbSelect.setEnabled(
            self.ui.cbSubjID.currentText() != ""
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

    #
    # Close event
    #
    def closeEvent(self, event):
        # Run the callback
        if self.on_close_callback:
            selsubject = self.subjlistfile.get_subject_info(self.ui.cbSubjID.currentText())
            self.on_close_callback(data=selsubject)
        return super().closeEvent(event)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    screate = SubjectSelector(onclosecb=lambda data: print(data))
    screate.show()
    sys.exit(app.exec_())
