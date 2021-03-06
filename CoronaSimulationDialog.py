import datetime
import numpy as np
from PyQt5.QtCore import pyqtSlot, QSettings
from matplotlib.ticker import FuncFormatter
from scipy.integrate import odeint
from PyQt5.QtWidgets import QDialog, QFileDialog
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import csv

from RtEstimator import RtEstimator
from gen.Ui_CoronaSimulationDialog import Ui_CoronaSimulationDialog


class CoronaSimulationDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self.ui = Ui_CoronaSimulationDialog()
        self.ui.setupUi(self)
        self.fig = Figure()
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.ax = self.canvas.figure.add_subplot(111)
        self.ui.figuresLayout.addWidget(self.canvas)
        self.showMaximized()

        self.N = 100000000  # Total population
        self.beta = .25  # Infection rate
        self.gamma = .15  # The Removal rate
        self.Ro = round(self.beta / self.gamma, 2)
        self.Rt = []
        self.a = .2  # Onset rate, the inverse of the incubation period
        self.actual_data = []
        self.simulation_days = 30
        self.days = []

        actual_data_file = QSettings().value("actual_data_file", "")
        if actual_data_file:
            self.load_actual_data_file(actual_data_file)

        self.ui.sliderRo.setValue(self.Ro * 100)
        self.ui.sliderGamma.setValue(.15 * 1000)
        self.ui.sliderBeta.setValue(.25 * 1000)
        self.reflect_params_to_ui()

        self.ui.sliderGamma.valueChanged.connect(self.gamma_value_changed)
        self.ui.sliderBeta.valueChanged.connect(self.beta_value_changed)
        self.ui.sliderRo.valueChanged.connect(self.r0_value_changed)

        self.start_execution()

    def gamma_value_changed(self):
        self.gamma = round((self.ui.sliderGamma.value()) / 1000.0, 3)
        self.Ro = round(self.beta / self.gamma, 2)
        self.blockSignals(True)
        self.ui.sliderRo.blockSignals(True)
        self.ui.sliderRo.setValue(self.Ro * 100)
        self.ui.sliderRo.blockSignals(False)
        self.reflect_params_to_ui()
        self.start_execution()

    def beta_value_changed(self):
        self.beta = round((self.ui.sliderBeta.value()) / 1000.0, 3)
        self.Ro = round(self.beta / self.gamma, 2)
        self.ui.sliderRo.blockSignals(True)
        self.ui.sliderRo.setValue(self.Ro * 100)
        self.ui.sliderRo.blockSignals(False)
        self.reflect_params_to_ui()
        self.start_execution()

    def r0_value_changed(self):
        self.Ro = round((self.ui.sliderRo.value()) / 100.0, 2)
        self.beta = round(self.Ro * self.gamma, 3)
        self.ui.sliderBeta.blockSignals(True)
        self.ui.sliderBeta.setValue(self.beta * 1000)
        self.ui.sliderBeta.blockSignals(False)
        self.reflect_params_to_ui()
        self.start_execution()

    def x_formatter(self, x, pos):
        if pos % 10 == 0:
            return self.days[x]
        return ''

    def y_formatter(self, x, pos):
        return '{:,}'.format(int(x))

    def start_execution(self):
        if len(self.actual_data) < 4:
            return

        days = self.actual_data[:, 0]
        days = [np.unicode(i) for i in days]
        actual_infected = self.actual_data[:, 1]
        actual_infected = [int(i) for i in actual_infected]
        first_day = days[0]

        I0 = actual_infected[len(actual_infected) - 1]
        R0 = 0
        S0 = self.N - I0 - R0

        base = datetime.datetime.strptime(first_day, '%Y-%m-%d')
        self.days = [(base + datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(len(actual_infected) + self.simulation_days)]

        t = np.linspace(0, self.simulation_days, self.simulation_days)
        i = self.run_sir_model(S0, I0, R0, t)
        i = np.delete(i, 0)
        peak_index = np.argmax(i) + len(actual_infected)
        actual_data_index = len(actual_infected)
        peak_day = self.days[peak_index]
        plot_start_day = self.days[actual_data_index - 3]

        self.ax.set_ylabel('Y')
        self.ax.cla()
        self.ax.xaxis.grid()
        self.ax.yaxis.grid()
        # self.ax.minorticks_on()
        self.ax.set_xticklabels(self.days, rotation=90)
        self.ax.xaxis.set_major_formatter(FuncFormatter(self.x_formatter))
        self.ax.yaxis.set_major_formatter(FuncFormatter(self.y_formatter))

        # self.ax.ticklabel_format(axis="x", style="plain")
        self.ax.plot(self.days[:len(actual_infected)], actual_infected, label='Actual')
        self.ax.plot(self.days[-len(i):], i, label='Expected')

        # self.ax.set_xlim(plot_start_day, peak_day)
        self.ax.legend(loc="upper right")
        self.canvas.draw_idle()

    def run_sir_model(self, s0, i0, r0, t):
        ret = odeint(self.derive_sir_model, (s0, i0, r0), t)
        return ret[:, 1]

    def derive_sir_model(self, y, t):
        s, i, r = y
        beta = self.Ro * self.gamma
        se = beta * s * i / self.N
        ir = self.gamma * i
        return -se, se - ir, ir

    def reflect_params_to_ui(self):
        self.ui.labelBeta.setText("Beta: " + str(self.beta))
        self.ui.labelRo.setText("Ro: " + str(self.Ro))
        self.ui.labelGamma.setText("Gamma: " + str(self.gamma))

    def load_actual_data_file(self, file_name):
        with open(file_name, newline='') as file:
            self.actual_data = list(csv.reader(file))
            self.actual_data = np.asarray(self.actual_data)

        self.ui.actualDataFileButton.setText('Actual Data File: ' + file_name)
        self.start_execution()

    @pyqtSlot()
    def actual_data_file_selected(self):
        t = QFileDialog.getOpenFileName(self, filter="csv(*.csv)")
        file_name = t[0]
        if file_name:
            QSettings().setValue("actual_data_file", file_name)
            self.load_actual_data_file(file_name)

    @pyqtSlot()
    def estimate_R(self):
        actual_infected = self.actual_data[:, 1]
        actual_infected = [int(i) for i in actual_infected]
        incidents = [actual_infected[0]]
        incidents.extend(np.diff(actual_infected))
        self.Rt = RtEstimator(incidents, 5.1, 1).estimR()
        if (len(self.Rt) > 0):
            self.Ro = self.Rt[0]
            for r in self.Rt:
                if r > 0:
                    self.Ro = r
            self.ui.sliderRo.setValue(self.Ro * 100)

    @pyqtSlot()
    def simulationDaysChanged(self):
        default = 30
        str = self.ui.lineEditSimulationDays.text()
        x = int(str)
        if x < 10:
            x = default
        if self.simulation_days != x:
            self.simulation_days = x
            self.start_execution()