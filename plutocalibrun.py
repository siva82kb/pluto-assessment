# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/plutocalib.ui'
#
# Created by: PyQt5 UI code generator 5.15.9
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_CalibrationWindow(object):
    def setupUi(self, CalibrationWindow):
        CalibrationWindow.setObjectName("CalibrationWindow")
        CalibrationWindow.resize(451, 90)
        CalibrationWindow.setMinimumSize(QtCore.QSize(451, 90))
        CalibrationWindow.setMaximumSize(QtCore.QSize(451, 90))
        self.centralwidget = QtWidgets.QWidget(CalibrationWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 10, 431, 73))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.lblInstruction = QtWidgets.QLabel(self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblInstruction.setFont(font)
        self.lblInstruction.setObjectName("lblInstruction")
        self.verticalLayout.addWidget(self.lblInstruction)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.lblInstruction_2 = QtWidgets.QLabel(self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblInstruction_2.setFont(font)
        self.lblInstruction_2.setStyleSheet("color: rgb(170, 0, 0);")
        self.lblInstruction_2.setObjectName("lblInstruction_2")
        self.horizontalLayout.addWidget(self.lblInstruction_2)
        self.lblCalibStatus = QtWidgets.QLabel(self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblCalibStatus.setFont(font)
        self.lblCalibStatus.setText("")
        self.lblCalibStatus.setObjectName("lblCalibStatus")
        self.horizontalLayout.addWidget(self.lblCalibStatus)
        self.lblInstruction_3 = QtWidgets.QLabel(self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblInstruction_3.setFont(font)
        self.lblInstruction_3.setStyleSheet("color: rgb(170, 0, 0);")
        self.lblInstruction_3.setObjectName("lblInstruction_3")
        self.horizontalLayout.addWidget(self.lblInstruction_3)
        self.lblHandDistance = QtWidgets.QLabel(self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblHandDistance.setFont(font)
        self.lblHandDistance.setText("")
        self.lblHandDistance.setObjectName("lblHandDistance")
        self.horizontalLayout.addWidget(self.lblHandDistance)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.lblInstruction2 = QtWidgets.QLabel(self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setFamily("Bahnschrift Light")
        font.setPointSize(12)
        self.lblInstruction2.setFont(font)
        self.lblInstruction2.setStyleSheet("color: rgb(0, 0, 127);")
        self.lblInstruction2.setText("")
        self.lblInstruction2.setAlignment(QtCore.Qt.AlignCenter)
        self.lblInstruction2.setObjectName("lblInstruction2")
        self.verticalLayout.addWidget(self.lblInstruction2)
        CalibrationWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(CalibrationWindow)
        QtCore.QMetaObject.connectSlotsByName(CalibrationWindow)

    def retranslateUi(self, CalibrationWindow):
        _translate = QtCore.QCoreApplication.translate
        CalibrationWindow.setWindowTitle(_translate("CalibrationWindow", "MainWindow"))
        self.lblInstruction.setText(_translate("CalibrationWindow", "Bring the two handles together and press the PLUTO Button"))
        self.lblInstruction_2.setText(_translate("CalibrationWindow", "Calibration:"))
        self.lblInstruction_3.setText(_translate("CalibrationWindow", "Handle Distance:"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    CalibrationWindow = QtWidgets.QMainWindow()
    ui = Ui_CalibrationWindow()
    ui.setupUi(CalibrationWindow)
    CalibrationWindow.show()
    sys.exit(app.exec_())
