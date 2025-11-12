import sys
import numpy as np
import sounddevice as sd
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

SAMPLE_RATE = 44100
CHUNK_SIZE = 2048
NUM_BARS = 64

def apply_hanning_window(audio_chunk):
    window = np.hanning(len(audio_chunk))
    return audio_chunk * window

def compute_fft_magnitude(windowed_audio):
    fft_data = np.fft.rfft(windowed_audio)
    magnitude = np.abs(fft_data)
    return magnitude

def convert_to_db(magnitude, floor=-60):
    magnitude = np.maximum(magnitude, 1e-10)
    db_magnitude = 20 * np.log10(magnitude)
    db_magnitude = np.maximum(db_magnitude, floor)
    return db_magnitude

def logarithmic_binning(magnitude_array, num_bars, sample_rate, chunk_size):
    freq_resolution = sample_rate / chunk_size
    num_fft_bins = len(magnitude_array)
    
    min_freq = 20
    max_freq = sample_rate / 2
    
    freq_edges = np.logspace(np.log10(min_freq), np.log10(max_freq), num_bars + 1)
    bin_edges = (freq_edges / freq_resolution).astype(int)
    bin_edges = np.clip(bin_edges, 0, num_fft_bins - 1)
    
    binned_data = np.zeros(num_bars)
    for i in range(num_bars):
        start_bin = bin_edges[i]
        end_bin = bin_edges[i + 1]
        
        if start_bin < end_bin:
            binned_data[i] = np.mean(magnitude_array[start_bin:end_bin])
        else:
            binned_data[i] = magnitude_array[start_bin]
    
    return binned_data

class DSPDashboard(QtWidgets.QWidget):
    
    def __init__(self):
        super().__init__()
        
        self.latest_raw_chunk = np.zeros(CHUNK_SIZE)
        self.latest_binned_data = np.zeros(NUM_BARS)
        self.data_lock = QtCore.QMutex()
        
        self.smoothed_data = np.zeros(NUM_BARS)
        self.smoothing_factor = 0.7
        
        self.init_ui()
        self.start_audio_stream()
        
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_realtime_plot)
        self.timer.start(30)
    
    def init_ui(self):
        self.setWindowTitle('Educational Real-Time Audio DSP Dashboard')
        self.setGeometry(100, 100, 1200, 900)
        
        main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(main_layout)
        
        realtime_label = QtWidgets.QLabel('Real-Time Spectrum Analyzer')
        realtime_label.setStyleSheet('font-size: 14pt; font-weight: bold;')
        main_layout.addWidget(realtime_label)
        
        self.realtime_plot = pg.PlotWidget()
        self.realtime_plot.setLabel('left', 'Linear Magnitude')
        self.realtime_plot.setLabel('bottom', 'Frequency Bins')
        self.realtime_plot.setTitle('Live Audio Spectrum (Logarithmic Frequency Scale)')
        self.realtime_plot.setYRange(0, 10)
        self.realtime_plot.showGrid(x=True, y=True, alpha=0.3)
        
        x_positions = np.arange(NUM_BARS)
        self.realtime_bars = pg.BarGraphItem(
            x=x_positions, 
            height=np.zeros(NUM_BARS), 
            width=0.8, 
            brush='g'
        )
        self.realtime_plot.addItem(self.realtime_bars)
        
        main_layout.addWidget(self.realtime_plot, stretch=2)
        
        snapshot_label = QtWidgets.QLabel('DSP Snapshot - Step-by-Step Pipeline')
        snapshot_label.setStyleSheet('font-size: 14pt; font-weight: bold;')
        main_layout.addWidget(snapshot_label)
        
        self.snapshot_button = QtWidgets.QPushButton('Take Snapshot')
        self.snapshot_button.setStyleSheet('font-size: 12pt; padding: 10px;')
        self.snapshot_button.clicked.connect(self.on_snapshot_click)
        main_layout.addWidget(self.snapshot_button)
        
        snapshot_widget = pg.GraphicsLayoutWidget()
        main_layout.addWidget(snapshot_widget, stretch=3)
        
        self.plot_fft_magnitude = snapshot_widget.addPlot(row=0, col=0)
        self.plot_fft_magnitude.setTitle('3. Raw FFT Magnitude (Frequency Domain)')
        self.plot_fft_magnitude.setLabel('left', 'Linear Magnitude')
        self.plot_fft_magnitude.setLabel('bottom', 'Frequency (Hz)')
        self.plot_fft_magnitude.showGrid(x=True, y=True, alpha=0.3)
        self.curve_fft_magnitude = self.plot_fft_magnitude.plot(pen='y')
        
        self.plot_binned = snapshot_widget.addPlot(row=0, col=1)
        self.plot_binned.setTitle('4. Log-Binned Magnitude (dB)')
        self.plot_binned.setLabel('left', 'Magnitude (dB)')
        self.plot_binned.setLabel('bottom', 'Frequency Bins')
        self.plot_binned.showGrid(x=True, y=True, alpha=0.3)
        self.bars_binned = pg.BarGraphItem(
            x=np.arange(NUM_BARS), 
            height=np.zeros(NUM_BARS), 
            width=0.8, 
            brush='c'
        )
        self.plot_binned.addItem(self.bars_binned)
        
        self.plot_raw_audio = snapshot_widget.addPlot(row=1, col=0)
        self.plot_raw_audio.setTitle('1. Raw Audio (Time Domain)')
        self.plot_raw_audio.setLabel('left', 'Amplitude')
        self.plot_raw_audio.setLabel('bottom', 'Time (samples)')
        self.plot_raw_audio.showGrid(x=True, y=True, alpha=0.3)
        self.curve_raw_audio = self.plot_raw_audio.plot(pen='r')
        
        self.plot_windowed = snapshot_widget.addPlot(row=1, col=1)
        self.plot_windowed.setTitle('2. Windowed Audio (Time Domain)')
        self.plot_windowed.setLabel('left', 'Amplitude')
        self.plot_windowed.setLabel('bottom', 'Time (samples)')
        self.plot_windowed.showGrid(x=True, y=True, alpha=0.3)
        self.curve_windowed = self.plot_windowed.plot(pen='m')
    
    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f'Audio stream status: {status}')
        
        if indata.ndim > 1:
            audio_chunk = indata[:, 0].flatten()
        else:
            audio_chunk = indata.flatten()
        
        if len(audio_chunk) != CHUNK_SIZE:
            return
        
        windowed_audio = apply_hanning_window(audio_chunk)
        magnitude = compute_fft_magnitude(windowed_audio)
        binned_data = logarithmic_binning(magnitude, NUM_BARS, SAMPLE_RATE, CHUNK_SIZE)
        
        self.data_lock.lock()
        try:
            self.latest_raw_chunk = audio_chunk.copy()
            self.latest_binned_data = binned_data.copy()
        finally:
            self.data_lock.unlock()
    
    def update_realtime_plot(self):
        self.data_lock.lock()
        try:
            binned_data = self.latest_binned_data.copy()
        finally:
            self.data_lock.unlock()
        
        self.smoothed_data = (self.smoothing_factor * self.smoothed_data + 
                             (1 - self.smoothing_factor) * binned_data)
        
        self.realtime_bars.setOpts(height=self.smoothed_data)
    
    def on_snapshot_click(self):
        self.data_lock.lock()
        try:
            raw_audio_chunk = self.latest_raw_chunk.copy()
        finally:
            self.data_lock.unlock()
        
        time_samples = np.arange(CHUNK_SIZE)
        windowed_audio_chunk = apply_hanning_window(raw_audio_chunk)
        fft_magnitude = compute_fft_magnitude(windowed_audio_chunk)
        freq_axis = np.linspace(0, SAMPLE_RATE / 2, len(fft_magnitude))
        
        binned_magnitude = logarithmic_binning(fft_magnitude, NUM_BARS, SAMPLE_RATE, CHUNK_SIZE)
        binned_db = convert_to_db(binned_magnitude)
        
        self.curve_raw_audio.setData(time_samples, raw_audio_chunk)
        self.curve_windowed.setData(time_samples, windowed_audio_chunk)
        self.curve_fft_magnitude.setData(freq_axis, fft_magnitude)
        self.bars_binned.setOpts(height=binned_db)
        
        print("Snapshot captured and DSP pipeline visualized!")
    
    def start_audio_stream(self):
        try:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=CHUNK_SIZE,
                channels=1,
                callback=self.audio_callback,
                dtype=np.float32
            )
            self.stream.start()
            print(f'Audio stream started: {SAMPLE_RATE} Hz, chunk size {CHUNK_SIZE}')
        except Exception as e:
            print(f'Error starting audio stream: {e}')
            QtWidgets.QMessageBox.critical(
                self, 
                'Audio Error', 
                f'Failed to start audio stream:\n{e}\n\nMake sure a microphone is connected.'
            )
    
    def closeEvent(self, event):
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    dashboard = DSPDashboard()
    dashboard.show()
    sys.exit(app.exec_() if hasattr(app, 'exec_') else app.exec())

if __name__ == '__main__':
    main()
