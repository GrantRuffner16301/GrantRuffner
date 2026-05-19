
# Deep Forest Bluetooth Inspector

A high-contrast, deep-green themed **Bluetooth Low Energy (BLE)** desktop application built with Python, PyQt6, and Bleak. It allows users to scan for nearby BLE devices in real-time, monitor signal strengths (RSSI) via a live moving-average graph, inspect GATT services/characteristics, and export historical RSSI logs to a CSV file.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![PyQt6](https://img.shields.io/badge/Framework-PyQt6-green.svg)
![Bleak](https://img.shields.io/badge/BLE-Bleak-lightblue.svg)

---

## 🌲 Features

* **Asynchronous Background Scanning:** Scans for BLE devices on a dedicated background thread without freezing the user interface.
* **Live RSSI Tracking & Smoothing:** Keeps an 80-sample rolling window of signal strength data and calculates a simple moving average (SMA) to filter out noise.
* **Signal Strength Heatmap:** Dynamically color-codes device signal rows based on proximity:
    * 🟩 **Strong (> -60 dBm)**
    * 🟨 **Medium (-60 to -80 dBm)**
    * 🟥 **Weak (< -80 dBm)**
* **GATT Service Inspector:** Click on any discovered device to spin up a worker thread, establish a connection, and query all available primary services and characteristics.
* **Live Visualization:** Renders a real-time `matplotlib` graph showing both the raw RSSI data points and the smoothed trendline.
* **Data Export:** Save collected RSSI trends to a standard CSV file for external analytical modeling or post-processing.
* **Custom Dark/Forest Aesthetic:** High-contrast palette curated for visibility and long inspection sessions.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.9 or higher installed. 

> **Note:** Bluetooth permissions vary by operating system. On macOS, ensure your terminal/IDE has Bluetooth access in System Settings. On Linux, you may need `bluez` installed and root/sudo privileges depending on your user group configurations.

### 2. Clone the Repository
```bash
git clone [https://github.com/GrantRuffner16301/GrantRuffner.git](https://github.com/GrantRuffner16301/GrantRuffner.git)
cd GrantRuffner/Bluetooth_Scanning

```

### 3. Install Dependencies
Install the required packages using pip:

```bash
pip install PyQt6 bleak matplotlib
```

### 🚀 Usage
Run the main script directly from your terminal:

```bash
python bluetooth_inspector.py
```

---

### How to use the interface:
  - Discover: The left table will automatically populate with active BLE devices broadcasting nearby.
  - Inspect: Click on any row to select a device. The right sidebar will immediately attempt a GATT connection to read its profiles
  - Analyze: Watch the live graph update in real-time as new advertisement packages are intercepted.
  - Save: Click the 💾 EXPORT HISTORY (CSV) button to save the current session's signal data to your machine.

---

### 📂 Code Architecture
  - The implementation splits workloads across dedicated threads to ensure the UI remains smooth and responsive:
    - BackgroundScanThread(QThread): Manages an independent asyncio event loop to handle continuous, non-blocking BleakScanner device discoveries.
    - GATTWorker(QThread): Connects asynchronously to a specific target MAC address, mapping out services and characteristic UUIDs on demand.
    - RSSIGraph(FigureCanvasQTAgg): Embedded Matplotlib canvas wrapping the visual mapping configurations.
    - MainWindow(QWidget): Coordinates the PyQt components, handles UI data state matching, holds the CSS stylesheets, and triggers CSV file exports.
    
---

### 📝 License
This project is open-source. Feel free to use, modify, and distribute it as needed.
