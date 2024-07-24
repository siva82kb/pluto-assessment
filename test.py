from PyQt5.QtCore import QThread, pyqtSignal, QObject


from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt5.QtCore import QThread, pyqtSignal, QObject

class Worker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self):
        super().__init__()

    def run(self):
        # Your actual work goes here
        for i in range(100):
            # Simulating work progress
            self.progress.emit(i)
            QThread.msleep(100)  # Simulate some work
        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Qt Thread Example')
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        self.label = QLabel('Progress:')
        layout.addWidget(self.label)

        self.button = QPushButton('Start Thread')
        layout.addWidget(self.button)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.worker = Worker()
        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progress.connect(self.update_progress)

        self.button.clicked.connect(self.start_thread)

    def start_thread(self):
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def update_progress(self, value):
        self.label.setText(f'Progress: {value}%')

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
