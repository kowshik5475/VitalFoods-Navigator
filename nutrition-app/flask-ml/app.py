import os
import sys

from flask import Flask, request, jsonify
from flask_cors import CORS

# Resolve dataset path relative to this file so it works regardless of cwd
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "dataset.csv")

# Defer model import so startup errors surface cleanly
from model import train_model, predict_diet

app = Flask(__name__)
CORS(app)

# ── Load model once at startup ─────────────────────────────────────────────
model_state: dict | None = None

if os.path.exists(CSV_PATH):
    try:
        model_state = train_model(CSV_PATH)
        print(f"[ML] Model ready. Accuracy: {model_state['accuracy']:.2%}", flush=True)
    except Exception as exc:
        print(f"[ML] Failed to train model: {exc}", flush=True)
else:
    print("[ML] dataset.csv not found — using rule-based fallback.", flush=True)
    print(f"[ML] Upload dataset.csv to: {CSV_PATH}", flush=True)


# ── Routes ──────────────────────────────────────────────────────────────────
@app.route("/ml-api/health")
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": model_state is not None,
        "accuracy": round(model_state["accuracy"], 4) if model_state else None,
    })


@app.route("/ml-api/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    try:
        diet = predict_diet(model_state, data)
    except Exception as exc:
        print(f"[ML] Prediction error: {exc}", flush=True)
        diet = "Balanced Diet"
    return jsonify({"diet": diet})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[ML] Flask ML API starting on port {port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False)
