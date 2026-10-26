# Accu-Chek Active Diabetes Management & Clinical Analytics Platform
### منصة قراءة وتحليل بيانات سكر الدم لجهاز Roche Accu-Chek Active عبر USB

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Protocol](https://img.shields.io/badge/Protocol-ISO%2FIEEE%2011073--20601%20%7C%2010417-emerald.svg)](https://standards.ieee.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask%203.1-orange.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-purple.svg)](https://github.com/)

---

## 🌍 Overview | نظرة عامة

### English:
The **Roche Accu-Chek Active** is one of the world's most widely used blood glucose meters. However, Roche has **officially discontinued** the consumer desktop software (*Accu-Chek 360°*), and the *Accu-Chek Active* hardware **lacks Bluetooth**, leaving millions of patients and physicians unable to sync or analyze their readings on modern PCs.

This open-source platform bridges that gap. It provides a complete, modern, privacy-first desktop solution that connects directly to the meter over USB using the **ISO/IEEE 11073-20601** personal health device standard. It visualizes readings with clinical consensus metrics (**TIR**, **GMI / eA1c**, **AGP 24h Profile**, **CV%**), supports printable medical reports, and exports data directly to Excel.

### العربية:
جهاز **Roche Accu-Chek Active** هو أحد أكثر أجهزة قياس سكر الدم انتشاراً وموثوقية في العالم. ولكن بعد قيام الشركة المصنعة (Roche) **بإيقاف برنامج الكمبيوتر المكتبي رسمياً (Accu-Chek 360°)**، ونظراً لأن جهاز Active **لا يحتوي على تقنية البلوتوث (يعمل بكابل USB فقط)**، وجد ملايين المرضى والأطباء صعوبة في سحب بياناتهم ومتابعتها على أجهزة الحاسوب الحديثة.

هذا المشروع هو منصة مفتوحة المصدر مجانية ومستقلة، توفر حلاً شاملاً يقرأ الجهاز مباشرة عبر منفذ USB بالمعيار الطبي الدولي المعتمد **ISO/IEEE 11073-20601**. توفر المنصة لوحة تحكم طبية متقدمة، وتحسب المؤشرات السريرية العالمية (**الوقت في الهدف السريري TIR**، **السكر التراكمي التقديري GMI**، **الملف الجلوكوزي الإسعافي AGP**، **معامل التباين CV**)، مع إمكانية طباعة تقرير سريري متكامل باللغة العربية وتصدير البيانات إلى **Excel**.

---

## ⚠️ Medical Safety Guarantee | ضمان الأمان الطبي

> **STRICTLY READ-ONLY ARCHITECTURE:**  
> This system communicates with the meter in strict read-only mode.  
> It **NEVER** attempts firmware updates, calibration modifications, or memory erasing.  
> Only standard read APDUs (`E2`/`E3`/`E4`, `01 03`, `0C 0D` / `0C 1C`, and `02 01`) are used. Commands such as `SET_TIME` (`0C 17`) and `ABORT` are blocked to guarantee device integrity.

---

## ✨ Key Features | المميزات الرئيسية

* **🩺 Clinical Diabetes Metrics (المعايير السريرية المعتمدة):**
  * **TIR (Time in Range):** Full 5-tier clinical consensus breakdown (<54, 54-69, 70-180, 181-250, >250 mg/dL).
  * **GMI (Glucose Management Indicator):** Formula-derived estimated HbA1c %.
  * **Variability (CV% & SD):** Evaluates glycemic stability (target $\le 36\%$).
* **📊 Interactive Analytics & Charts (الرسوم البيانية التفاعلية):**
  * Chronological Glucose Trend timeline with clinical threshold bands.
  * 24-Hour AGP Modal Profile (Ambulatory Glucose Profile) detecting daytime/nocturnal hypoglycemia.
  * Meal and time-of-day slots breakdown (Dawn, Morning, Afternoon, Evening, Night).
* **🔢 Physical Memory Index Preservation (الحفاظ على تسلسل الذاكرة):**
  * Automatically handles clock changes or year skips (e.g. 2024 vs 2026) by offering ordering by physical hardware memory index (`Index`) or timestamp.
* **⏱️ Smart Year/Time Correction (+Years Offset):**
  * One-click correction for meters with misconfigured years without altering daily patterns or time intervals.
* **📄 Print-Ready Arabic Clinical Report (تقرير طبي سريري جاهز للطباعة):**
  * Clean, formatted medical report ready to be saved as PDF or printed for endocrinologists and physicians.
* **📥 Excel / CSV Export (تصدير إكسل):**
  * Direct CSV export with UTF-8 BOM encoding ensuring perfect Arabic character rendering in Microsoft Excel.
* **🔒 100% Offline & Private (أمان وخصوصية تامة):**
  * Operates locally on your PC. No cloud accounts, no subscriptions, and zero patient data uploaded to external servers.

---

## 🚀 Quick Start | طريقة التشغيل السريع

### Requirements | المتطلبات:
* **Operating System:** Windows 10/11 or Linux.
* **Python:** 3.10 or higher.
* **Cable:** Standard Micro-USB data cable (ensure it supports data transfer, not charge-only).

### 1. Installation | التثبيت:
```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/accu-chek-active-platform.git
cd accu-chek-active-platform

# Install dependencies
pip install -r requirements.txt
```

### 2. Running on Windows | التشغيل على ويندوز:
Double-click `start_server.bat` (or `تشغيل_منصة_ACCU-CHEK.bat`), or run in terminal:
```bash
python server.py
```
Open **[http://localhost:5050](http://localhost:5050)** in your browser.

---

## 🔌 Driver Setup (Windows & Linux) | إعداد برامج التشغيل

### Windows:
Accu-Chek Active uses the USB Personal Healthcare Device Class (PHDC). To allow Windows user-mode applications to read from it:
1. Connect the meter via USB (the meter screen will display **`PC`**).
2. Click **"تثبيت برنامج تشغيل الجهاز (WinUSB)"** on the dashboard (or launch `zadig-2.9.exe`).
3. The included `zadig.ini` preset will automatically select `Accu-Chek Active USB` (`VID 0x173A, PID 0x21CC`).
4. Click **Install Driver** (or **Replace Driver**).
5. Done! Return to the dashboard and click **"قراءة وسحب بيانات الجهاز الآن"**.

### Linux:
Install the udev rule to allow reading without root permissions:
```bash
sudo cp core/udev/99-accuchek.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## 🛠️ Project Architecture | هيكلية المشروع

```text
ACCU-CHEK/
├── core/                       # ISO/IEEE 11073-20601 protocol engine & parser
│   ├── src/                    # Device communication, association, APDUs
│   ├── tests/                  # 145+ comprehensive protocol unit tests
│   ├── examples/               # Synthetic fixtures for offline development
│   └── udev/                   # Linux udev rules
├── templates/
│   ├── index.html              # Modern dark-mode Arabic/English medical dashboard
│   └── report_ar.html          # Print-ready medical clinical report
├── data/                       # Local data storage (excluded from Git for privacy)
├── accu_service.py             # Windows PnP detection, WinUSB check, clinical analytics
├── server.py                   # Flask REST API and web application server
├── zadig-2.9.exe               # Microsoft WinUSB helper utility
├── zadig.ini                   # Pre-configured Zadig hardware profile
├── start_server.bat            # Universal 1-click launcher
├── تشغيل_منصة_ACCU-CHEK.bat     # Arabic 1-click launcher
├── requirements.txt            # Python dependencies
├── CONTRIBUTING.md             # Contribution guidelines
├── LICENSE                     # MIT License
└── README.md                   # Project documentation
```

---

## 🧪 Testing | تشغيل الاختبارات

The protocol engine includes a test suite covering APDU encoding, segment reconstruction, status flags, and association lifecycles:

```bash
# Windows
cmd /c "set PYTHONPATH=core && python -m pytest core/tests"

# Linux / macOS
PYTHONPATH=core pytest core/tests
```

---

## 🤝 Acknowledgements | شكر وتقدير

This platform stands on the shoulders of the open-source diabetes and medical device reverse-engineering community:
* Original protocol documentation and reverse-engineering research by **Tidepool** (`tidepool-org/uploader`).
* Protocol implementation foundations by **Henrique Gouveia** (`accu-chek-active-linux`).
* The IEEE 11073 Personal Health Data (PHDC) standard committees.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) - feel free to use, modify, and distribute for personal, educational, and clinical research purposes.
