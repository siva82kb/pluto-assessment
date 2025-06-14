"""Module containing some of my custom PyQt5 widgets.

Author: Sivakumar Balasubramanian
Date: 08 June 2025
"""

from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QTextEdit,
    QDialogButtonBox, QLabel, QMessageBox
)
from PyQt5.QtWidgets import QGraphicsPathItem
from PyQt5.QtGui import QPainterPath, QBrush, QColor
from PyQt5.QtCore import QPointF
import pyqtgraph as pg
import math

from PyQt5.QtGui import QFont
import sys

class SingleLineWrapTextEdit(QTextEdit):
    """A QTextEdit that behaves like a single-line input with visual word wrapping."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptRichText(False)
        self.setWordWrapMode(QtGui.QTextOption.WordWrap)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(130)  # Simulates single-line height

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            event.ignore()  # Block newline entry
        else:
            super().keyPressEvent(event)


class CommentDialog(QDialog):
    def __init__(self, parent=None, label="Commemnt: ", optionyesno=False,
                 ):
        super().__init__(parent)
        self.setFixedSize(300, 200)
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.CustomizeWindowHint)
        self.setWindowTitle(f"Comment Logger.")

        # Set global font
        font = QtGui.QFont()
        font.setFamily("Cascadia Mono Light")
        font.setPointSize(8)
        self.setFont(font)

        # Create label
        self.label = QLabel(label, self)

        # Create visually wrapping single-line input
        self.text_edit = SingleLineWrapTextEdit(self)
        self.text_edit.setPlaceholderText("Type comment...")

        # OK/Cancel buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
            if optionyesno else QDialogButtonBox.Cancel,
            self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # Rename the buttons
        cancel_button = self.button_box.button(QDialogButtonBox.Cancel)
        cancel_button.setText("Reject")
        cancel_button.setAutoDefault(False)

        if optionyesno:
            ok_button = self.button_box.button(QDialogButtonBox.Ok)
            ok_button.setText("Accept")
            ok_button.setAutoDefault(False)

        # Prevent Return key from triggering OK
        self.button_box.button(QDialogButtonBox.Cancel).setAutoDefault(False)
        if optionyesno:
            self.button_box.button(QDialogButtonBox.Ok).setAutoDefault(False)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.button_box)

    def getText(self):
        # Just in case, ensure newlines are removed
        return self.text_edit.toPlainText().replace('\n', ' ').strip()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            event.ignore()  # Block dialog-level return behavior
        else:
            super().keyPressEvent(event)
    
    def accept(self):
        self.text_edit.setStyleSheet("")
        super().accept()
    
    def reject(self):
        comment = self.getText()
        if not comment:
            QMessageBox.warning(self, "Empty Comment", "Please enter a comment before continuing.")
            # You can also show a QMessageBox if you want feedback
            self.text_edit.setFocus()
            self.text_edit.setStyleSheet("border: 1px solid red;")
        else:
            self.text_edit.setStyleSheet("")  # Reset border
            super().reject()


class MechTaskSkipDialog(QDialog):
    def __init__(self, parent=None, label="Commemnt: "):
        super().__init__(parent)
        self.setFixedSize(300, 200)
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.CustomizeWindowHint)
        self.setWindowTitle(f"Skip Mechanism/Task.")

        # Set global font
        font = QtGui.QFont()
        font.setFamily("Cascadia Mono Light")
        font.setPointSize(8)
        self.setFont(font)

        # Create label
        self.label = QLabel(label, self)

        # Create visually wrapping single-line input
        self.text_edit = SingleLineWrapTextEdit(self)
        self.text_edit.setPlaceholderText("Type comment...")

        # OK/Cancel buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # Rename the buttons
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        ok_button.setText("Skip")
        ok_button.setAutoDefault(False)
        cancel_button = self.button_box.button(QDialogButtonBox.Cancel)
        cancel_button.setText("Don't Skip")
        cancel_button.setAutoDefault(False)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.button_box)

    def getText(self):
        # Just in case, ensure newlines are removed
        return self.text_edit.toPlainText().replace('\n', ' ').strip()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            event.ignore()  # Block dialog-level return behavior
        else:
            super().keyPressEvent(event)
    
    def accept(self):
        comment = self.getText()
        if not comment:
            QMessageBox.warning(self, "Empty Comment", "Please enter a comment before skipping.")
            # You can also show a QMessageBox if you want feedback
            self.text_edit.setFocus()
            self.text_edit.setStyleSheet("border: 1px solid red;")
        else:
            self.text_edit.setStyleSheet("")  # Reset border
            super().accept()
    
    def reject(self):
        self.text_edit.setStyleSheet("")
        super().reject()


def create_sector(center, radius, start_angle_deg, span_angle_deg, color=QColor(255, 0, 0, 100)):
    """
    Create a QGraphicsPathItem representing a filled sector.

    Parameters:
        center (QPointF): Center of the sector.
        radius (float): Radius of the sector.
        start_angle_deg (float): Starting angle in degrees (0° = right, counterclockwise).
        span_angle_deg (float): Angular span in degrees.
        color (QColor): Fill color of the sector.

    Returns:
        QGraphicsPathItem
    """
    path = QPainterPath()
    path.moveTo(center)

    # Add arc
    path.arcTo(center.x() - radius, center.y() - radius,
               2 * radius, 2 * radius,
               -start_angle_deg, -span_angle_deg)  # Negative for clockwise

    path.lineTo(center)  # Close back to center

    item = QGraphicsPathItem(path)
    item.setBrush(QBrush(color))
    item.setPen(pg.mkPen(None))
    return item


# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)
    f""
    dialog = CommentDialog(
        label="Reason for skipping Left limb HOC for 1234:",
        optionyesno=False
    )
    if dialog.exec_() == QDialog.Accepted:
        print("Input:", dialog.getText())
    else:
        print("Cancelled")
