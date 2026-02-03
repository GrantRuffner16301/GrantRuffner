import sys
import asyncio
import csv
from datetime import datetime
from collections import defaultdict, deque

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QFrame,
    QListWidget, QListWidgetItem, QTextEdit, QHeaderView,
    QPushButton, QFileDialog, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush, QFont, QPalette

from bleak import BleakScanner, BleakClient

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

# ---------------------------------------------------------
#  Constants & Helpers
# ---------------------------------------------------------
OUI_DB = {
    "A4:83:E7": "Apple", "F4:5C:89": "Apple", "D0:03:4B": "Samsung",
    "00:1A:7D": "Apple", "3C:5A:B4": "Sony", "9C:1D:58": "Bose",
    "C0:28:8D": "Microsoft", "E8:EB:1B": "Fitbit", "C8:47:8C": "Tile",
}

SMOOTHING_WINDOW = 5 

def lookup_manufacturer(mac: str) -> str:
    prefix = mac.upper()[0:8]
    return OUI_DB.get(prefix, "Unknown")

def decode_beacon(meta_dict: dict) -> str:
    mdata = meta_dict.get("manufacturer_data") or {}
    # Simple iBeacon check
    if 0x004C in mdata:
        return "<span style='color: #A5D6A7;'>Apple/iBeacon Detected</span>"
    return "No specialized beacon data"

# ---------------------------------------------------------
#  Worker Threads
# ---------------------------------------------------------
class BackgroundScanThread(QThread):
    results_ready = pyqtSignal(list)

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                devices = self.loop.run_until_complete(self.scan())
                self.results_ready.emit(devices)
            except Exception as e: 
                print(f"Scan Error: {e}")
            self.msleep(2500)

    async def scan(self):
        found = await BleakScanner.discover(timeout=1.5, return_adv=True)
        results = []
        for addr, (device, adv_data) in found.items():
            results.append({
                "name": device.name or adv_data.local_name or "Unknown",
                "address": device.address,
                "rssi": adv_data.rssi,
                "metadata": {"manufacturer_data": adv_data.manufacturer_data}
            })
        return results

class GATTWorker(QThread):
    services_ready = pyqtSignal(object, str)
    def __init__(self, mac):
        super().__init__()
        self.mac = mac

    def run(self):
        try:
            services = asyncio.run(self.load_services())
            self.services_ready.emit(services, "")
        except Exception as e: self.services_ready.emit(None, str(e))

    async def load_services(self):
        async with BleakClient(self.mac, timeout=10.0) as client:
            return await client.get_services()

# ---------------------------------------------------------
#  Main UI
# ---------------------------------------------------------
class RSSIGraph(FigureCanvasQTAgg):
    def __init__(self):
        self.fig = Figure(figsize=(4, 3), dpi=100, facecolor='#2D3E2F')
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1B261C')
        self.ax.set_title("Signal Strength Trend", color='#E8F5E9', weight='bold')
        self.raw_line, = self.ax.plot([], [], "o", markersize=3, color='#81C784', label='Raw', alpha=0.3)
        self.smooth_line, = self.ax.plot([], [], "-", linewidth=2, color='#00E5FF', label='Smooth')
        self.ax.tick_params(colors='#E8F5E9')
        for spine in self.ax.spines.values(): spine.set_edgecolor('#444')
        self.ax.grid(True, linestyle='--', alpha=0.1, color='white')
        self.fig.tight_layout()

    def update_graph(self, raw_data, smooth_data):
        if not raw_data: return
        self.raw_line.set_data(range(len(raw_data)), raw_data)
        self.smooth_line.set_data(range(len(smooth_data)), smooth_data)
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Deep Forest Bluetooth Inspector")
        self.resize(1100, 800)
        
        # UI Stylesheet - High Contrast Deep Green
        self.setStyleSheet("""
            QWidget { background-color: #2D3E2F; color: #E8F5E9; font-family: 'Segoe UI'; }
            QTableWidget { 
                background-color: #1B261C; 
                border: 1px solid #3E5441; 
                gridline-color: #2D3E2F; 
                selection-background-color: #4CAF50; 
                selection-color: white;
            }
            QHeaderView::section { background-color: #253327; color: #A5D6A7; padding: 6px; border: 1px solid #3E5441; }
            QListWidget { background-color: #1B261C; border: 1px solid #3E5441; }
            QTextEdit { background-color: #1B261C; border: 1px solid #3E5441; color: #00E5FF; }
            QPushButton { background-color: #3E5441; color: white; border-radius: 4px; padding: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #4CAF50; }
        """)

        self.rssi_history = defaultdict(lambda: deque(maxlen=80))
        self.smooth_history = defaultdict(lambda: deque(maxlen=80))
        self.device_meta = {}
        self.address_to_row = {}
        self.selected_mac = None

        main_layout = QHBoxLayout(self)

        # Left Column
        left = QVBoxLayout()
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Device Name", "MAC Address", "Signal Strength"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # --- THE FIX: DISABLE EDITING ---
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        self.table.cellClicked.connect(self.device_selected)
        left.addWidget(self.table)
        main_layout.addLayout(left, 2)

        # Right Column
        sidebar = QVBoxLayout()
        self.info_panel = QLabel("Click a device to inspect signal...")
        self.info_panel.setStyleSheet("padding: 15px; background: #1B261C; border-radius: 8px; border-left: 5px solid #4CAF50;")
        self.info_panel.setWordWrap(True)
        sidebar.addWidget(self.info_panel)

        self.export_btn = QPushButton("💾 EXPORT HISTORY (CSV)")
        self.export_btn.clicked.connect(self.export_to_csv)
        sidebar.addWidget(self.export_btn)

        sidebar.addWidget(QLabel("<b>AVAILABLE SERVICES</b>"))
        self.service_list = QListWidget()
        self.service_list.itemClicked.connect(self.service_selected)
        sidebar.addWidget(self.service_list)

        self.char_view = QTextEdit()
        self.char_view.setReadOnly(True)
        sidebar.addWidget(self.char_view)

        self.graph = RSSIGraph()
        sidebar.addWidget(self.graph)
        main_layout.addLayout(sidebar, 1)

        # Background Tasks
        self.scanner = BackgroundScanThread()
        self.scanner.results_ready.connect(self.update_devices)
        self.scanner.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_graph)
        self.timer.start(800)

    def update_devices(self, devices):
        for d in devices:
            addr, rssi, name = d["address"], d["rssi"], d["name"]
            self.device_meta[addr] = d["metadata"]

            if rssi:
                self.rssi_history[addr].append(rssi)
                # Calculate simple moving average
                samples = list(self.rssi_history[addr])[-SMOOTHING_WINDOW:]
                avg = round(sum(samples) / len(samples), 1)
                self.smooth_history[addr].append(avg)
            else:
                avg = "N/A"

            if addr not in self.address_to_row:
                row = self.table.rowCount()
                self.address_to_row[addr] = row
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(name))
                self.table.setItem(row, 1, QTableWidgetItem(addr))
                self.table.setItem(row, 2, QTableWidgetItem(str(avg)))
            else:
                row = self.address_to_row[addr]
                self.table.item(row, 0).setText(name)
                self.table.item(row, 2).setText(str(avg))

            # Heatmap Colors
            if isinstance(avg, float):
                item = self.table.item(row, 2)
                if avg > -60:   color, txt = "#2E7D32", "white" # Strong
                elif avg > -80: color, txt = "#FBC02D", "black" # Med
                else:           color, txt = "#C62828", "white" # Weak
                item.setBackground(QBrush(QColor(color)))
                item.setForeground(QBrush(QColor(txt)))

    def device_selected(self, row, col):
        name = self.table.item(row, 0).text()
        mac = self.table.item(row, 1).text()
        self.selected_mac = mac
        
        beacon = decode_beacon(self.device_meta.get(mac, {}))
        self.info_panel.setText(
            f"<b style='font-size: 16px; color: #A5D6A7;'>{name}</b><br>"
            f"<span style='color: #888;'>{mac}</span><br><br>"
            f"<b>Manufacturer:</b> {lookup_manufacturer(mac)}<br>"
            f"<b>Status:</b> {beacon}<br><br>"
            f"<i style='color: #00E5FF;'>Attempting GATT connection...</i>"
        )
        
        self.worker = GATTWorker(mac)
        self.worker.services_ready.connect(self.display_services)
        self.worker.start()

    def display_services(self, services, error):
        self.service_list.clear()
        if error or services is None:
            self.service_list.addItem(f"Connect Failed: {error if error else 'Timeout'}")
            return
        for s in services:
            item = QListWidgetItem(f"Srv: {s.uuid[-12:]}") # Show last 12 chars for readability
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.service_list.addItem(item)

    def service_selected(self, item):
        srv = item.data(Qt.ItemDataRole.UserRole)
        res = f"Service: {srv.uuid}\n" + ("="*20) + "\n"
        for c in srv.characteristics:
            res += f"Char: {c.uuid[-12:]}\nProps: {c.properties}\n\n"
        self.char_view.setText(res)

    def refresh_graph(self):
        if self.selected_mac:
            raw = list(self.rssi_history[self.selected_mac])
            smooth = list(self.smooth_history[self.selected_mac])
            self.graph.update_graph(raw, smooth)

    def export_to_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save RSSI Log", "", "CSV Files (*.csv)")
        if path:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["MAC", "RSSI_Trend"])
                for mac, hist in self.rssi_history.items():
                    writer.writerow([mac, list(hist)])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())