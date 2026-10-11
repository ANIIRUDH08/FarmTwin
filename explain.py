"""Explanations for FarmTwin (browser build).

template_explanation() is rule-based and works with no internet.
ai_explanation() calls the Gemini API directly over HTTPS, so it only works while the
device is online. When offline it returns the OFFLINE marker and the app shows a
friendly note instead of an error.
"""
import json
import time
import urllib.error
import urllib.request

W, C, Y, N = "Water use (m³)", "Cultivation cost (₹)", "Yield (kg)", "Net returns (₹)"

MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-3.5-flash"]
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

OFFLINE = "__offline__"      # returned when there is no internet connection

SYSTEM_PROMPT = (
    "You explain farm scenario results to farmers in simple language. "
    "Use ONLY the numbers provided. Never invent figures. "
    "For each scenario say what it improves and what it gives up compared with the baseline. "
    "Mention that results are estimates based on documented assumptions. "
    "Keep it under 150 words."
)


def is_online():
    """True if the browser says it has a connection (always True when run on a normal PC)."""
    try:
        import js   # only exists inside the browser (Pyodide)
        return bool(js.navigator.onLine)
    except Exception:
        return True


def template_explanation(rows):
    """Rule-based explanation. Works without internet or an API key."""
    base = rows[0]
    lines = []

    for r in rows[1:]:
        dw = r[W] - base[W]
        dc = r[C] - base[C]
        dy = r[Y] - base[Y]
        dn = r[N] - base[N]

        def change(x, label, unit="", prefix=""):
            if x == 0:
                return f"{label} unchanged"
            return f"{label} {'up' if x > 0 else 'down'} by {prefix}{abs(x):,}{unit}"

        lines.append(
            f"**{r['Scenario']}** vs baseline: "
            f"{change(dw, 'water', ' m³')}, "
            f"{change(dc, 'cost', prefix='₹')}, "
            f"{change(dy, 'yield', ' kg')}, "
            f"{change(dn, 'net returns', prefix='₹')}."
        )

    def winners(key, pick):
        target = pick(r[key] for r in rows)
        return [r["Scenario"] for r in rows if r[key] == target]

    water_w, yield_w, net_w = winners(W, min), winners(Y, max), winners(N, max)

    lines.append("")
    lines.append(f"- Least water: **{', '.join(water_w)}**")
    lines.append(f"- Highest yield: **{', '.join(yield_w)}**")
    lines.append(f"- Highest net returns: **{', '.join(net_w)}**")

    if not (set(water_w) & set(yield_w) & set(net_w)):
        lines.append("- No single scenario is best on all three metrics.")

    return "\n".join(lines)


def _api_key():
    """The key lives in api_key.py (see README). Returns None if it hasn't been filled in."""
    try:
        from api_key import GEMINI_API_KEY
    except Exception:
        return None
    key = (GEMINI_API_KEY or "").strip()
    if not key or key.upper().startswith("PASTE"):
        return None
    return key


def _generate(model, key, prompt, low_thinking, timeout=20):
    """One call to the Gemini REST API. Returns the text, or raises on any problem."""
    gen = {"maxOutputTokens": 2048}
    if low_thinking:
        # 2.5 models use a token budget, newer ones use a level
        gen["thinkingConfig"] = ({"thinkingBudget": 0} if "2.5" in model
                                 else {"thinkingLevel": "low"})
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": gen,
    }
    req = urllib.request.Request(
        API_URL.format(model=model),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


def ai_explanation(rows, farm_summary):
    """Gemini explanation.

    Returns: the text, None (no API key set), OFFLINE (no internet),
    or a short '(AI explanation failed: ...)' message.
    """
    key = _api_key()
    if not key:
        return None
    if not is_online():
        return OFFLINE

    table = "\n".join(str(r) for r in rows)
    prompt = f"Farm: {farm_summary}\n\nScenario results:\n{table}"

    retry_words = ("503", "unavailable", "timed out", "timeout", "deadline", "429")
    last_error = None

    for model in MODELS_TO_TRY:
        for attempt in range(2):
            try:
                text = _generate(model, key, prompt, low_thinking=(attempt == 0))
                if text:
                    return text
            except Exception as e:           # any error: try again, then the next model
                last_error = e
                if any(w in str(e).lower() for w in retry_words):
                    time.sleep(1)

    if not is_online():                      # connection dropped while we were trying
        return OFFLINE
    return f"(AI explanation failed: {last_error})"
