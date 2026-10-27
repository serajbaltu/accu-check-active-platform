# Accu-Chek Active Diabetes Management & Clinical Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Protocol](https://img.shields.io/badge/Protocol-ISO%2FIEEE%2011073--20601%20%7C%2010417-emerald.svg)](https://standards.ieee.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask%203.1-orange.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-purple.svg)](https://github.com/)

---

## 🌍 Overview

The **Roche Accu-Chek Active** is one of the world's most widely used blood glucose meters. However, Roche has **officially discontinued** its consumer desktop software (*Accu-Chek 360°*), and the *Accu-Chek Active* hardware **lacks Bluetooth** (communicating exclusively over a Micro-USB cable), leaving millions of patients and healthcare providers unable to sync or analyze their readings on modern operating systems.

This open-source platform bridges that gap. It provides a complete, modern, privacy-first desktop solution that connects directly to the meter over USB using the **ISO/IEEE 11073-20601** personal health device standard. It calculates international consensus metrics (**TIR**, **GMI / eA1c**, **AGP 24-Hour Profile**, **CV%**), supports printable medical clinical reports, provides customizable target ranges, and exports data directly to CSV / Excel.

---

## ⚠️ Medical Safety Guarantee

> **STRICTLY READ-ONLY ARCHITECTURE:**  
> This system communicates with the meter in strict read-only mode.  
> It **NEVER** attempts firmware updates, calibration modifications, or memory erasing.  
> Only standard read APDUs (`E2`/`E3`/`E4`, `01 03`, `0C 0D` / `0C 1C`, and `02 01`) are used. Commands such as `SET_TIME` (`0C 17`) and `ABORT` are blocked to guarantee physical device integrity.

---

## ✨ Key Features

* **🩺 Clinical Diabetes Metrics:**
  * **TIR (Time in Range):** Full 5-tier clinical consensus breakdown (<54, 54-69, 70-180, 181-250, >250 mg/dL).
  * **GMI (Glucose Management Indicator):** Formula-derived estimated HbA1c %.
  * **Variability (CV% & SD):** Evaluates glycemic stability (consensus target $\le 36\%$).
  * **Customizable Target Ranges:** Easily adjust clinical target thresholds (e.g. 70-140, 70-180 mg/dL) with instantaneous metric recalculation.
* **📊 Interactive Analytics & Charts:**
  * Chronological Glucose Trend timeline with clinical threshold bands.
  * 24-Hour AGP Modal Profile (Ambulatory Glucose Profile) detecting daytime and nocturnal hypoglycemia patterns.
  * Meal and time-of-day slots breakdown (Dawn, Morning, Afternoon, Evening, Night).
* **🔢 Physical Hardware Index Preservation:**
  * Displays the true physical memory sequence (`Index 1..500`) stored inside the meter.
  * Interactive multi-column sorting by Index or Timestamp to easily resolve historical meter clock shifts or incorrect dates.
* **📄 Print-Ready Medical Clinical Report:**
  * Formatted clinical report ready to be saved as PDF or printed for endocrinologists and physicians.
* **📥 Excel / CSV Export:**
  * Direct CSV export with UTF-8 BOM encoding ensuring seamless compatibility with Microsoft Excel.
* **🔒 100% Offline & Private:**
  * Operates locally on your PC. No cloud accounts, no subscriptions, and zero patient data uploaded to external servers.

---

## 🚀 Quick Start

### Requirements:
* **Operating System:** Windows 10/11 or Linux.
* **Python:** 3.10 or higher.
* **Cable:** Standard Micro-USB data cable (ensure it supports data transfer, not charge-only).

### 1. Installation:
```bash
# Clone the repository
git clone https://github.com/serajbaltu/accu-check-active-platform.git
cd accu-check-active-platform

# Install dependencies
pip install -r requirements.txt
```

### 2. Running on Windows:
Double-click `start_server.bat` or run in terminal:
```bash
python server.py
```
Open **[http://localhost:5050](http://localhost:5050)** in your browser.

---

## 🔌 Driver Setup (Windows & Linux)

### Windows:
Accu-Chek Active uses the USB Personal Healthcare Device Class (PHDC). To allow Windows user-mode applications to communicate with it:
1. Connect the meter via USB (the meter screen will display **`PC`**).
2. Click **"Install WinUSB Driver"** on the dashboard (or launch `zadig-2.9.exe`).
3. The included `zadig.ini` preset will automatically select `Accu-Chek Active USB` (`VID 0x173A, PID 0x21CC`).
4. Click **Install Driver** (or **Replace Driver**).
5. Done! Return to the dashboard and click **"Read Device Data Now"**.

### Linux:
Install the udev rule to allow reading without root permissions:
```bash
sudo cp core/udev/99-accuchek.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## 🛠️ Project Architecture

```text
ACCU-CHEK/
├── core/                       # ISO/IEEE 11073-20601 protocol engine & parser
│   ├── src/                    # Device communication, association, APDUs
│   ├── tests/                  # 145+ comprehensive protocol unit tests
│   ├── examples/               # Synthetic fixtures for offline development
│   └── udev/                   # Linux udev rules
├── templates/
│   ├── index.html              # Modern clinical diabetes dashboard
│   └── report.html             # Print-ready medical clinical report
├── data/                       # Local data storage (excluded from Git for privacy)
├── accu_service.py             # Windows PnP detection, WinUSB check, clinical analytics
├── server.py                   # Flask REST API and web application server
├── zadig-2.9.exe               # Microsoft WinUSB helper utility
├── zadig.ini                   # Pre-configured Zadig hardware profile
├── start_server.bat            # Universal 1-click launcher
├── requirements.txt            # Python dependencies
├── CONTRIBUTING.md             # Contribution guidelines
├── LICENSE                     # MIT License
└── README.md                   # Project documentation
```

---

## 🧪 Testing

The protocol engine includes a test suite covering APDU encoding, segment reconstruction, status flags, and association lifecycles:

```bash
# Windows
cmd /c "set PYTHONPATH=core && python -m pytest core/tests"

# Linux / macOS
PYTHONPATH=core pytest core/tests
```

---

## 🤝 Acknowledgements

This platform stands on the shoulders of the open-source diabetes and medical device reverse-engineering community:
* Original protocol documentation and reverse-engineering research by **Tidepool** (`tidepool-org/uploader`).
* Protocol implementation foundations by **Henrique Gouveia** (`accu-chek-active-linux`).
* The IEEE 11073 Personal Health Data (PHDC) standard committees.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) - feel free to use, modify, and distribute for personal, educational, and clinical research purposes.
