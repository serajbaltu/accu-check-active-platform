"""
Accu-Chek Active USB Service & Protocol Interface for Windows
Supports detection, WinUSB check, direct IEEE 11073-20601 read, and data management.
"""

from __future__ import annotations

import os
import sys
import json
import subprocess
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add core engine to sys.path so we can import protocol engine
BASE_DIR = Path(__file__).resolve().parent
CORE_DIR = BASE_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

VID_ROCHE = 0x173A
PID_ACTIVE = 0x21CC


def check_windows_pnp_status() -> Dict[str, Any]:
    """
    Queries Windows Registry and libusb natively to check if Accu-Chek Active
    is physically connected and whether WinUSB driver is ready.
    """
    import winreg
    try:
        import libusb_package
        import usb.core
        backend = libusb_package.get_libusb1_backend()
        dev = usb.core.find(idVendor=VID_ROCHE, idProduct=PID_ACTIVE, backend=backend)
        if dev is not None:
            return {
                "connected": True,
                "driver_installed": True,
                "name": "Accu-Chek Active USB",
                "instance_id": "VID_173A&PID_21CC",
                "status": "OK",
                "message": "جهاز Accu-Chek متصل وتعريف WinUSB جاهز للاتصال المباشر!"
            }
    except Exception:
        pass

    # Check via Windows Registry
    try:
        key_path = r"SYSTEM\CurrentControlSet\Enum\USB\VID_173A&PID_21CC"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
            sub_count, _, _ = winreg.QueryInfoKey(k)
            if sub_count == 0:
                return {
                    "connected": False,
                    "driver_installed": False,
                    "name": None,
                    "status": "NOT_CONNECTED",
                    "message": "جهاز Accu-Chek غير متصل بمنفذ USB."
                }
            
            instance_name = winreg.EnumKey(k, 0)
            with winreg.OpenKey(k, instance_name) as dev_key:
                vals = {}
                num_vals = winreg.QueryInfoKey(dev_key)[1]
                for i in range(num_vals):
                    vname, vdata, _ = winreg.EnumValue(dev_key, i)
                    vals[vname] = vdata

                desc = vals.get("DeviceDesc", "Accu-Chek Active USB")
                cfg_flags = vals.get("ConfigFlags", 0)
                service = vals.get("Service", "")

                # ConfigFlags & 0x40 means failed install (driver missing)
                driver_missing = bool(cfg_flags & 0x40) or (not service)

                if driver_missing:
                    return {
                        "connected": True,
                        "driver_installed": False,
                        "name": desc,
                        "instance_id": instance_name,
                        "status": "NEED_DRIVER",
                        "message": "الجهاز متصل بنجاح، ولكن يتطلب تثبيت تعريف WinUSB للتمكن من قراءة البيانات."
                    }
                else:
                    return {
                        "connected": True,
                        "driver_installed": True,
                        "name": desc,
                        "instance_id": instance_name,
                        "status": "OK",
                        "service": service,
                        "message": "الجهاز متصل وبرنامج التشغيل مثبت وجاهز للاستخدام."
                    }

    except FileNotFoundError:
        return {
            "connected": False,
            "driver_installed": False,
            "name": None,
            "status": "NOT_CONNECTED",
            "message": "جهاز Accu-Chek غير متصل بمنفذ USB."
        }
    except Exception as e:
        return {
            "connected": False,
            "driver_installed": False,
            "name": None,
            "status": "ERROR",
            "message": f"خطأ أثناء فحص حالة الجهاز: {e}"
        }


def launch_zadig_installer() -> Dict[str, Any]:
    """
    Launches Zadig 2.9 with Administrator elevation to install WinUSB driver for Accu-Chek.
    """
    zadig_path = BASE_DIR / "zadig-2.9.exe"
    if not zadig_path.exists():
        return {"success": False, "error": "ملف zadig-2.9.exe غير موجود."}
        
    ps_cmd = f'Start-Process -FilePath "{zadig_path}" -Verb RunAs'
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            cwd=str(BASE_DIR)
        )
        return {
            "success": True,
            "message": "تم تشغيل مثبت التعريفات Zadig بنجاح. يرجى تأكيد إذن الإدارة ثم الضغط على Install Driver."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_device_records(timeout_ms: int = 10000, wait_seconds: int = 15) -> Dict[str, Any]:
    """
    Communicates with the Accu-Chek Active meter over USB using ISO/IEEE 11073-20601 protocol.
    """
    try:
        import libusb_package
        from src.device import Device, DeviceNotFoundError, DeviceTimeoutError
        from src.association import associate, release
        from src.transfer import get_device_info, read_segment_entries
        from src.parser import parse_entries
    except ImportError as e:
        return {"success": False, "error": f"تعذر استيراد مكتبات البروتوكول: {e}"}

    start_time = datetime.datetime.now()
    device = None

    # Try opening device
    while True:
        try:
            device = Device.open(timeout_ms=timeout_ms)
            break
        except DeviceNotFoundError:
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            if elapsed >= wait_seconds:
                return {
                    "success": False,
                    "error": (
                        "لم يتم العثور على الجهاز عبر USB. "
                        "تأكد من: 1) تثبيت تعريف WinUSB، 2) توصيل الكابل وظهور كلمة 'PC' على شاشة الجهاز."
                    )
                }
            import time
            time.sleep(1.0)
        except Exception as e:
            return {"success": False, "error": f"خطأ أثناء فتح الجهاز: {e}"}

    try:
        with device:
            # Phase 1: Association Handshake
            assoc_info = associate(device)
            
            # Phase 2: Device Attributes (Model, Serial, Device Time)
            dev_info = get_device_info(device)
            
            # Phase 3: Read measurement segments
            raw_entries = read_segment_entries(device, dev_info.seg_instance)
            
            # Phase 4: Clean release
            release(device)

            # Parse readings into structured records
            records = parse_entries(raw_entries)
            
            data = {
                "device": {
                    "vendor_id": VID_ROCHE,
                    "product_id": PID_ACTIVE,
                    "model": dev_info.model_number,
                    "serial": dev_info.serial_number,
                    "device_time": dev_info.device_time.isoformat() if dev_info.device_time else None
                },
                "read_at": datetime.datetime.now().isoformat(),
                "count": len(records),
                "records": [
                    {
                        "index": r.index,
                        "timestamp": r.timestamp.isoformat(),
                        "epoch": int(r.timestamp.timestamp()),
                        "mg_dL": r.mg_dL,
                        "mmol_L": round(r.mg_dL / 18.0182, 2),
                        "status": r.status
                    }
                    for r in records
                ]
            }

            # Save to last_sync.json
            save_path = BASE_DIR / "data" / "last_sync.json"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return {
                "success": True,
                "data": data,
                "message": f"تمت قراءة {len(records)} قياساً بنجاح من جهاز Accu-Chek Active!"
            }

    except Exception as e:
        return {"success": False, "error": f"فشل أثناء سحب البيانات من الجهاز: {str(e)}"}


def apply_year_offset(records: List[Dict[str, Any]], offset_years: int) -> List[Dict[str, Any]]:
    """
    Adjusts record timestamps by a specified number of years (e.g. +2 years to fix 2024 -> 2026).
    """
    if not offset_years:
        return records
    adjusted = []
    for r in records:
        r_copy = dict(r)
        ts_str = r.get("timestamp")
        if ts_str:
            try:
                dt = datetime.datetime.fromisoformat(ts_str)
                new_year = dt.year + offset_years
                try:
                    new_dt = dt.replace(year=new_year)
                except ValueError:
                    new_dt = dt.replace(year=new_year, day=28)
                r_copy["timestamp"] = new_dt.isoformat()
                r_copy["epoch"] = int(new_dt.timestamp())
                r_copy["original_timestamp"] = ts_str
            except Exception:
                pass
        adjusted.append(r_copy)
    return adjusted


def get_current_data(offset_years: int = 0) -> Dict[str, Any]:
    """
    Returns latest saved data or falls back to synthetic sample data,
    with optional year offset correction.
    """
    data = None
    last_sync = BASE_DIR / "data" / "last_sync.json"
    if last_sync.exists():
        try:
            with open(last_sync, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["is_synthetic"] = False
        except Exception:
            pass
            
    # Fallback to sample data
    if data is None:
        sample_path = CORE_DIR / "examples" / "data_sintetico.json"
        if sample_path.exists():
            try:
                with open(sample_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for r in data.get("records", []):
                        if "mg/dL" in r and "mg_dL" not in r:
                            r["mg_dL"] = r["mg/dL"]
                        if "mmol/L" in r and "mmol_L" not in r:
                            r["mmol_L"] = r["mmol/L"]
                    data["is_synthetic"] = True
            except Exception:
                pass

    if data is None:
        data = {
            "device": {"model": "2102", "serial": "DEMO-123456"},
            "count": 0,
            "records": [],
            "is_synthetic": True
        }

    if offset_years != 0 and "records" in data:
        data["records"] = apply_year_offset(data["records"], offset_years)
        data["applied_year_offset"] = offset_years

    return data


def compute_clinical_analytics(
    records: List[Dict[str, Any]],
    target_min: int = 70,
    target_max: int = 180,
    severe_low: int = 54,
    severe_high: int = 250
) -> Dict[str, Any]:
    """
    Calculates international standard diabetes clinical indicators:
    TIR with customizable target thresholds, GMI (estimated HbA1c), Mean, SD, CV, Hypo/Hyper counts, time of day.
    """
    if not records:
        return {
            "total_count": 0,
            "mean_mg_dl": 0,
            "mean_mmol_l": 0,
            "gmi_percent": 0,
            "sd": 0,
            "cv_percent": 0,
            "cv_target_met": True,
            "target_range": {
                "min": target_min,
                "max": target_max,
                "severe_low": severe_low,
                "severe_high": severe_high
            },
            "tir": {"very_low": 0, "low": 0, "in_range": 0, "high": 0, "very_high": 0},
            "tir_percentages": {"very_low": 0, "low": 0, "in_range": 0, "high": 0, "very_high": 0},
            "hypo_count": 0,
            "severe_hypo_count": 0,
            "time_slots": {}
        }

    values = [r["mg_dL"] for r in records if "mg_dL" in r and r["mg_dL"] > 0]
    n = len(values)
    if n == 0:
        return compute_clinical_analytics([], target_min, target_max, severe_low, severe_high)

    mean_mg = sum(values) / n
    mean_mmol = round(mean_mg / 18.0182, 2)
    
    # GMI (Estimated HbA1c) = 3.31 + (0.02392 * mean_mg_dl)
    gmi = round(3.31 + (0.02392 * mean_mg), 1)

    # Standard Deviation
    variance = sum((x - mean_mg) ** 2 for x in values) / (n - 1 if n > 1 else 1)
    sd = round(variance ** 0.5, 1)

    # Coefficient of Variation (CV %) = (SD / Mean) * 100
    cv = round((sd / mean_mg) * 100, 1) if mean_mg > 0 else 0
    cv_target_met = (cv <= 36.0) # Clinical target is <= 36%

    # Time In Range (TIR) with customizable thresholds
    very_low = sum(1 for x in values if x < severe_low)
    low = sum(1 for x in values if severe_low <= x < target_min)
    in_range = sum(1 for x in values if target_min <= x <= target_max)
    high = sum(1 for x in values if target_max < x <= severe_high)
    very_high = sum(1 for x in values if x > severe_high)
    hypo_count = sum(1 for x in values if x < target_min)

    tir = {
        "very_low": very_low,
        "low": low,
        "in_range": in_range,
        "high": high,
        "very_high": very_high
    }

    tir_pct = {
        "very_low": round((very_low / n) * 100, 1),
        "low": round((low / n) * 100, 1),
        "in_range": round((in_range / n) * 100, 1),
        "high": round((high / n) * 100, 1),
        "very_high": round((very_high / n) * 100, 1)
    }

    # Time slots breakdown
    # Morning/Fasting: 06:00 - 10:00
    # Midday: 10:00 - 14:00
    # Afternoon: 14:00 - 18:00
    # Evening: 18:00 - 23:00
    # Night: 23:00 - 06:00
    slots = {"morning": [], "midday": [], "afternoon": [], "evening": [], "night": []}
    for r in records:
        ts_str = r.get("timestamp")
        if not ts_str:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts_str)
            h = dt.hour
            v = r["mg_dL"]
            if 6 <= h < 10:
                slots["morning"].append(v)
            elif 10 <= h < 14:
                slots["midday"].append(v)
            elif 14 <= h < 18:
                slots["afternoon"].append(v)
            elif 18 <= h < 23:
                slots["evening"].append(v)
            else:
                slots["night"].append(v)
        except Exception:
            pass

    time_slots_summary = {}
    for slot_name, vals in slots.items():
        time_slots_summary[slot_name] = {
            "count": len(vals),
            "mean": round(sum(vals) / len(vals), 1) if vals else 0
        }

    return {
        "total_count": n,
        "mean_mg_dl": round(mean_mg, 1),
        "mean_mmol_l": mean_mmol,
        "gmi_percent": gmi,
        "sd": sd,
        "cv_percent": cv,
        "cv_target_met": cv_target_met,
        "tir": tir,
        "tir_percentages": tir_pct,
        "hypo_count": very_low + low,
        "severe_hypo_count": very_low,
        "hyper_count": high + very_high,
        "severe_hyper_count": very_high,
        "target_range": {
            "min": target_min,
            "max": target_max,
            "severe_low": severe_low,
            "severe_high": severe_high
        },
        "time_slots": time_slots_summary
    }
