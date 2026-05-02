import json
import os
from datetime import datetime
from typing import Optional
from flask import Flask, jsonify, request, abort
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config["JSON_SORT_KEYS"] = False

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

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


def load_data():
    if not os.path.exists(DATA_FILE):
        return DEFAULT_DATA.copy()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return {
            "bathroom_map": data.get("bathroom_map", DEFAULT_DATA["bathroom_map"]),
            "use_history": data.get("use_history", []),
        }
    except (json.JSONDecodeError, OSError):
        return DEFAULT_DATA.copy()


def save_data():
    data = {"bathroom_map": bathroom_map, "use_history": use_history}
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


data = load_data()
bathroom_map = data["bathroom_map"]
use_history = data["use_history"]


def get_all_bathrooms():
    bathrooms = []
    for building, entries in bathroom_map.items():
        for bathroom in entries:
            bathrooms.append({"building": building, **bathroom})
    return bathrooms


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
        normalized_building = building.strip().lower()
        results = [entry for entry in results if entry["building"].strip().lower() == normalized_building]
    if bathroom_id:
        normalized_id = bathroom_id.strip().lower()
        results = [entry for entry in results if entry["bathroom_id"].strip().lower() == normalized_id]
    return results


@app.route("/api/buildings", methods=["GET"])
def list_buildings():
    return jsonify({"buildings": list(bathroom_map.keys())})


@app.route("/api/status", methods=["GET"])
def get_status():
    buildings = []
    for building, bathrooms in bathroom_map.items():
        buildings.append({
            "name": building,
            "bathrooms": bathrooms,
        })
    return jsonify({"buildings": buildings})


@app.route("/api/bathrooms", methods=["GET"])
def list_bathrooms():
    building = request.args.get("building")
    if building:
        _, bathrooms = find_building(building)
        if bathrooms is None:
            abort(404, description=f"Building '{building}' not found")
        return jsonify({"building": building, "bathrooms": bathrooms})

    return jsonify({"bathrooms": get_all_bathrooms()})


@app.route("/api/bathrooms/<building>", methods=["GET"])
def bathrooms_by_building(building):
    found_building, bathrooms = find_building(building)
    if bathrooms is None:
        abort(404, description=f"Building '{building}' not found")
    return jsonify({"building": found_building, "bathrooms": bathrooms})


@app.route("/api/usage", methods=["GET"])
def list_usage_history():
    building = request.args.get("building")
    bathroom_id = request.args.get("bathroom_id")
    history = filter_usage_history(building, bathroom_id)
    return jsonify({"usage_history": history})


@app.route("/api/usage", methods=["POST"])
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
    save_data()
    return jsonify({"success": True, "entry": entry}), 201


@app.route("/api/bathrooms", methods=["POST"])
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

    save_data()
    return jsonify({"success": True, "building": building, "bathroom": bathroom}), 201


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
