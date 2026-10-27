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
    target_min = int(request.args.get("target_min", 70))
    target_max = int(request.args.get("target_max", 180))
    severe_low = int(request.args.get("severe_low", 54))
    severe_high = int(request.args.get("severe_high", 250))

    raw_data = accu_service.get_current_data(offset_years=offset_years)
    records = raw_data.get("records", [])
    analytics = accu_service.compute_clinical_analytics(
        records,
        target_min=target_min,
        target_max=target_max,
        severe_low=severe_low,
        severe_high=severe_high
    )
    return jsonify({
        "device": raw_data.get("device", {}),
        "read_at": raw_data.get("read_at"),
        "count": len(records),
        "is_synthetic": raw_data.get("is_synthetic", False),
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
    return jsonify({"success": True, "message": "Sample demonstration data loaded successfully."})

@app.route("/api/export-csv")
def api_export_csv():
    target_min = int(request.args.get("target_min", 70))
    target_max = int(request.args.get("target_max", 180))
    raw_data = accu_service.get_current_data(offset_years=0)
    records = raw_data.get("records", [])
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Index", "Timestamp", "Blood_Glucose_mg_dL", "Blood_Glucose_mmol_L", "Status_Code", "Clinical_Category"])
    
    for r in records:
        mg = r.get("mg_dL", 0)
        mmol = r.get("mmol_L", round(mg / 18.0182, 2))
        if mg < 54:
            cat = "Severe Hypo (< 54 mg/dL)"
        elif mg < target_min:
            cat = f"Low (< {target_min} mg/dL)"
        elif mg <= target_max:
            cat = f"In Target Range ({target_min}-{target_max} mg/dL)"
        elif mg <= 250:
            cat = f"High (> {target_max} mg/dL)"
        else:
            cat = "Severe Hyper (> 250 mg/dL)"
            
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
        "\ufeff" + output.getvalue(), # UTF-8 BOM for Excel support
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=accu_chek_readings.csv"}
    )

@app.route("/report")
def serve_report():
    return render_template("report.html")

if __name__ == "__main__":
    port = 5050
    print(f"Starting Accu-Chek Dashboard on http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
