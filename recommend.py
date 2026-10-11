"""Crop recommendation. Loads crop_model.joblib; if that can't be loaded (for example the
browser's scikit-learn version differs from the one used for training), it trains the
same kind of model once from Crop_recommendation.csv instead."""
import pandas as pd

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
_bundle = None


def _train_from_csv():
    from sklearn.ensemble import RandomForestClassifier
    df = pd.read_csv("Crop_recommendation.csv")
    df.columns = [c.strip() for c in df.columns]
    lookup = {c.lower(): c for c in df.columns}
    cols = [lookup[f.lower()] for f in FEATURES]
    label = lookup.get("label", df.columns[-1])
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1)
    model.fit(df[cols].rename(columns=dict(zip(cols, FEATURES))), df[label])
    return {"model": model, "features": FEATURES}


def load():
    global _bundle
    if _bundle is None:
        try:
            import joblib
            _bundle = joblib.load("crop_model.joblib")
        except Exception:
            _bundle = _train_from_csv()
    return _bundle


def top_crops(n, p, k, temperature, humidity, ph, rainfall, top=3):
    b = load()
    X = pd.DataFrame([[n, p, k, temperature, humidity, ph, rainfall]],
                     columns=b["features"])
    probs = b["model"].predict_proba(X)[0]
    order = probs.argsort()[::-1][:top]
    return [(b["model"].classes_[i], float(probs[i])) for i in order]
