"""
Accu-Chek Active Diabetes Management & Analytics Web Server
"""

import os
import sys
import csv
import io
import json
import webbrowser
from pathlib import Path
from flask import Flask, render_template, jsonify, request, Response, send_file

import accu_service

app = Flask(__name__, template_folder="templates", static_folder="static")
BASE_DIR = Path(__file__).resolve().parent

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    status = accu_service.check_windows_pnp_status()
    return jsonify(status)

@app.route("/api/install-driver", methods=["POST"])
def api_install_driver():
    res = accu_service.launch_zadig_installer()
    return jsonify(res)

@app.route("/api/data")
def api_data():
    offset_years = int(request.args.get("offset_years", 0))
    raw_data = accu_service.get_current_data(offset_years=offset_years)
    records = raw_data.get("records", [])
    analytics = accu_service.compute_clinical_analytics(records)
    return jsonify({
        "device": raw_data.get("device", {}),
        "read_at": raw_data.get("read_at"),
        "count": len(records),
        "is_synthetic": raw_data.get("is_synthetic", False),
        "applied_year_offset": raw_data.get("applied_year_offset", 0),
        "records": records,
        "analytics": analytics
    })

@app.route("/api/sync", methods=["POST"])
def api_sync():
    timeout = int(request.args.get("timeout", 10000))
    wait = int(request.args.get("wait", 15))
    res = accu_service.read_device_records(timeout_ms=timeout, wait_seconds=wait)
    return jsonify(res)

@app.route("/api/load-sample", methods=["POST"])
def api_load_sample():
    # Remove last_sync.json if exists to revert to sample data
    sync_file = BASE_DIR / "data" / "last_sync.json"
    if sync_file.exists():
        try:
            sync_file.unlink()
        except Exception:
            pass
    return jsonify({"success": True, "message": "تم تحميل البيانات النموذجية بنجاح."})

@app.route("/api/export-csv")
def api_export_csv():
    offset_years = int(request.args.get("offset_years", 0))
    raw_data = accu_service.get_current_data(offset_years=offset_years)
    records = raw_data.get("records", [])
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Index", "Timestamp", "Blood_Glucose_mg_dL", "Blood_Glucose_mmol_L", "Status_Code", "Clinical_Category"])
    
    for r in records:
        mg = r.get("mg_dL", 0)
        mmol = r.get("mmol_L", round(mg / 18.0182, 2))
        if mg < 54:
            cat = "هبوط حاد جداً (Very Low)"
        elif mg < 70:
            cat = "هبوط (Low)"
        elif mg <= 180:
            cat = "النطاق المستهدف (In Range)"
        elif mg <= 250:
            cat = "ارتفاع (High)"
        else:
            cat = "ارتفاع حاد جداً (Very High)"
            
        writer.writerow([
            r.get("index", ""),
            r.get("timestamp", ""),
            mg,
            mmol,
            r.get("status", 0),
            cat
        ])
        
    output.seek(0)
    return Response(
        "\ufeff" + output.getvalue(), # UTF-8 BOM for Arabic support in Excel
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=accu_chek_readings.csv"}
    )

@app.route("/report")
def serve_report():
    return render_template("report_ar.html")

if __name__ == "__main__":
    port = 5050
    print(f"Starting Accu-Chek Dashboard on http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
