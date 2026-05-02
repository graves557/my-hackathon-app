import json
import os
from datetime import datetime
from typing import Optional
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
 
app = Flask(__name__)
CORS(app)
app.config["JSON_SORT_KEYS"] = False
 
# ---------------------------------------------------------------------------
# Data layer
# On Vercel, the filesystem is read-only in production, so we keep an
# in-memory store seeded from DEFAULT_DATA. If you want persistence, swap
# this out for a database (e.g. Vercel Postgres, PlanetScale, Upstash Redis).
# ---------------------------------------------------------------------------
 
DEFAULT_DATA = {
    "bathroom_map": {
        "Science Hall": [
            {"id": "SH-101", "name": "North Restroom", "floor": 1, "status": "open", "cleanliness": "good"},
            {"id": "SH-201", "name": "South Restroom", "floor": 2, "status": "closed", "cleanliness": "fair"},
        ],
        "Library": [
            {"id": "LIB-1", "name": "Main Restroom", "floor": 1, "status": "open", "cleanliness": "excellent"},
        ],
        "Student Center": [
            {"id": "SC-1A", "name": "East Restroom", "floor": 1, "status": "open", "cleanliness": "good"},
            {"id": "SC-2B", "name": "West Restroom", "floor": 2, "status": "open", "cleanliness": "fair"},
        ],
    },
    "use_history": [],
}
 
# Deep-copy so mutations don't affect DEFAULT_DATA
import copy
bathroom_map = copy.deepcopy(DEFAULT_DATA["bathroom_map"])
use_history = []
 
 
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
 
def get_all_bathrooms():
    result = []
    for building, entries in bathroom_map.items():
        for bathroom in entries:
            result.append({"building": building, **bathroom})
    return result
 
 
def find_building(building_name: str):
    normalized = building_name.strip().lower()
    for building, bathrooms in bathroom_map.items():
        if building.lower() == normalized:
            return building, bathrooms
    return None, None
 
 
def find_bathroom(building_name: str, bathroom_id: str):
    building, bathrooms = find_building(building_name)
    if bathrooms is None:
        return None, None, None
    normalized_id = bathroom_id.strip().lower()
    for bathroom in bathrooms:
        if str(bathroom.get("id", "")).strip().lower() == normalized_id:
            return building, bathrooms, bathroom
    return building, bathrooms, None
 
 
def filter_usage_history(building: Optional[str] = None, bathroom_id: Optional[str] = None):
    results = use_history
    if building:
        nb = building.strip().lower()
        results = [e for e in results if e["building"].strip().lower() == nb]
    if bathroom_id:
        nid = bathroom_id.strip().lower()
        results = [e for e in results if e["bathroom_id"].strip().lower() == nid]
    return results
 
 
# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
 
@app.route("/buildings", methods=["GET"])
def list_buildings():
    return jsonify({"buildings": list(bathroom_map.keys())})
 
 
@app.route("/buildings", methods=["POST"])
def create_building():
    if not request.is_json:
        abort(400, description="Request body must be JSON")
    payload = request.get_json()
    building_name = payload.get("name")
    bathroom = payload.get("bathroom")
    if not building_name:
        abort(400, description="Request JSON must include 'name'")
    found_building, _ = find_building(building_name)
    if found_building:
        abort(400, description=f"Building '{building_name}' already exists")
    bathroom_map[building_name] = [bathroom] if bathroom else []
    return jsonify({
        "success": True,
        "building": building_name,
        "bathrooms": bathroom_map[building_name],
    }), 201
 
 
@app.route("/status", methods=["GET"])
def get_status():
    buildings = [
        {"name": building, "bathrooms": bathrooms}
        for building, bathrooms in bathroom_map.items()
    ]
    return jsonify({"buildings": buildings})
 
 
@app.route("/bathrooms", methods=["GET"])
def list_bathrooms():
    building = request.args.get("building")
    if building:
        _, bathrooms = find_building(building)
        if bathrooms is None:
            abort(404, description=f"Building '{building}' not found")
        return jsonify({"building": building, "bathrooms": bathrooms})
    return jsonify({"bathrooms": get_all_bathrooms()})
 
 
@app.route("/bathrooms/<building>", methods=["GET"])
def bathrooms_by_building(building):
    found_building, bathrooms = find_building(building)
    if bathrooms is None:
        abort(404, description=f"Building '{building}' not found")
    return jsonify({"building": found_building, "bathrooms": bathrooms})
 
 
@app.route("/usage", methods=["GET"])
def list_usage_history():
    building = request.args.get("building")
    bathroom_id = request.args.get("bathroom_id")
    history = filter_usage_history(building, bathroom_id)
    return jsonify({"usage_history": history})
 
 
@app.route("/usage", methods=["POST"])
def log_usage_event():
    if not request.is_json:
        abort(400, description="Request body must be JSON")
    payload = request.get_json()
    building = payload.get("building")
    bathroom_id = payload.get("bathroom_id")
    event = payload.get("event", "used")
    note = payload.get("note")
    if not building or not bathroom_id:
        abort(400, description="Request JSON must include 'building' and 'bathroom_id'")
    found_building, _, bathroom = find_bathroom(building, bathroom_id)
    if bathroom is None:
        abort(404, description=f"Bathroom '{bathroom_id}' in building '{building}' not found")
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "building": found_building,
        "bathroom_id": bathroom_id,
        "bathroom_name": bathroom.get("name"),
        "event": event,
        "note": note,
    }
    use_history.append(entry)
    return jsonify({"success": True, "entry": entry}), 201
 
 
@app.route("/bathrooms", methods=["POST"])
def add_bathroom():
    if not request.is_json:
        abort(400, description="Request body must be JSON")
    payload = request.get_json()
    building = payload.get("building")
    bathroom = payload.get("bathroom")
    if not building or not bathroom:
        abort(400, description="Request JSON must include 'building' and 'bathroom'")
    _, bathrooms = find_building(building)
    if bathrooms is None:
        bathroom_map[building] = [bathroom]
    else:
        bathrooms.append(bathroom)
    return jsonify({"success": True, "building": building, "bathroom": bathroom}), 201
 
 
# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
 
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404
 
 
@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400
 
 
# ---------------------------------------------------------------------------
# Local dev entry point  (not used by Vercel — Vercel imports `app` directly)
# ---------------------------------------------------------------------------
 
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)