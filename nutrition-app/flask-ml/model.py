import re
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score


# ── Column name cleaning ────────────────────────────────────────────────────
def _clean_col(name: str) -> str:
    """Strip leading 'N. ' number prefix and surrounding whitespace."""
    name = name.strip()
    name = re.sub(r"^\d+\.\s*", "", name)
    return name.strip()


# ── Columns we can collect from the frontend form ──────────────────────────
# Maps frontend JSON key  →  cleaned CSV column name
FIELD_MAP = {
    "age":        "Age",
    "weight":     "Weight (in kg)",
    "height":     "Height (in cm)",
    "activity":   "Activity Level",
    "preference": "Food Preference",
    "meals":      "Meals per day",
    "goal":       "What is your goal?",
}

# Cleaned name of the target column in the dataset
TARGET_COL = "Which diet do you think suits you best?"

# Columns that exist in the dataset but are NOT in the form → drop them
DROP_COLS = {
    "Gender",
    "Average Sleep (hours per day)",
    "How often do you eat junk food?",
}


def train_model(csv_path: str) -> dict:
    df = pd.read_csv(csv_path)

    # Clean column names
    df.columns = [_clean_col(c) for c in df.columns]

    # Drop any all-NaN trailing columns (artifact of trailing commas in CSV)
    df = df.dropna(axis=1, how="all")

    # Drop "Timestamp" if present
    if "Timestamp" in df.columns:
        df = df.drop("Timestamp", axis=1)

    # Drop columns not available from the frontend
    for col in DROP_COLS:
        if col in df.columns:
            df = df.drop(col, axis=1)

    # Strip whitespace from all string-like columns first
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].astype(str).str.strip()

    # Encode all non-numeric columns with LabelEncoder
    encoders: dict[str, LabelEncoder] = {}
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col])
            encoders[col] = le

    if TARGET_COL not in df.columns:
        raise ValueError(
            f"Target column '{TARGET_COL}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    X = df.drop(TARGET_COL, axis=1)
    y = df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = DecisionTreeClassifier()
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, y_pred))
    print(f"[ML] Model trained on {len(df)} rows. Accuracy: {accuracy:.2%}", flush=True)
    print(f"[ML] Features: {list(X.columns)}", flush=True)

    return {
        "model": model,
        "encoders": encoders,
        "feature_columns": list(X.columns),
        "accuracy": accuracy,
    }


def _encode_value(val, encoder: LabelEncoder):
    """Encode a single value; return 0 if unseen."""
    try:
        return int(encoder.transform([str(val).strip()])[0])
    except Exception:
        return 0


def predict_diet(model_state: dict | None, user_data: dict) -> str:
    """
    user_data: dict with frontend field names (age, weight, height, activity,
               goal, preference, meals)
    Returns: predicted diet label string
    """
    if model_state is None:
        # Rule-based fallback when no model is loaded
        goal = user_data.get("goal", "")
        if goal == "Weight Gain":
            return "High Protein Diet"
        if goal == "Weight Loss":
            return "Low Carb Diet"
        return "Balanced Diet"

    model: DecisionTreeClassifier = model_state["model"]
    encoders: dict = model_state["encoders"]
    feature_columns: list = model_state["feature_columns"]
    output_encoder: LabelEncoder | None = encoders.get(TARGET_COL)

    row = {}
    for csv_col in feature_columns:
        # Find the matching frontend key for this CSV column
        frontend_key = next(
            (k for k, v in FIELD_MAP.items() if v == csv_col), None
        )
        val = user_data.get(frontend_key) if frontend_key else None
        if val is None:
            val = 0
        if csv_col in encoders:
            val = _encode_value(val, encoders[csv_col])
        else:
            try:
                val = float(val)
            except (TypeError, ValueError):
                val = 0
        row[csv_col] = val

    X = pd.DataFrame([row], columns=feature_columns)
    pred = model.predict(X)[0]

    if output_encoder is not None:
        label = output_encoder.inverse_transform([int(pred)])[0]
    else:
        label = str(pred)

    return label
