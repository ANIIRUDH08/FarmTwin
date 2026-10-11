"""Explanations for FarmTwin (browser build).

template_explanation() is rule-based and works with no internet.
ai_explanation() calls the Gemini API directly over HTTPS, so it only works while the
device is online. When offline it returns the OFFLINE marker and the app shows a
friendly note instead of an error.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

W, C, Y, N = "Water use (m³)", "Cultivation cost (₹)", "Yield (kg)", "Net returns (₹)"

MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-3.5-flash"]
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
VERTEX_URL = "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"

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


def _endpoints(key):
    """Which web addresses to try. AIza... keys use the Gemini API; AQ. keys are Google Cloud
    (Vertex AI) keys, so those try the Vertex address first."""
    if key.startswith("AQ."):
        return [VERTEX_URL, API_URL]
    return [API_URL]


def _post(url, key, body, timeout):
    """POST the request and return the parsed JSON, or raise a readable error."""
    full = url + "?key=" + urllib.parse.quote(key, safe="")
    req = urllib.request.Request(
        full,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8"))["error"]["message"]
        except Exception:
            msg = e.reason
        raise RuntimeError(f"HTTP {e.code}: {msg}")
    data = json.loads(raw)
    if isinstance(data, dict) and "error" in data:        # server answered with an error
        err = data["error"] or {}
        raise RuntimeError(f"{err.get('code', '')} {err.get('status', '')}: "
                           f"{err.get('message', 'unknown error')}")
    return data


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

    errors = []
    data = None
    for url in _endpoints(key):
        try:
            data = _post(url.format(model=model), key, body, timeout)
            break
        except Exception as e:
            errors.append(str(e))
    if data is None:
        raise RuntimeError(f"{model}: " + " | ".join(errors))

    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason") or "empty response"
        raise RuntimeError(f"{model}: no answer returned ({reason})")
    cand = candidates[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise RuntimeError(f"{model}: empty answer (finishReason: {cand.get('finishReason')})")
    return text


def _hint(message):
    """Plain-language hint for the most common problems."""
    m = message.lower()
    if "401" in m or "unauthenticated" in m:
        return (" The key was not accepted. A Gemini key starts with AIza (create one at "
                "aistudio.google.com/apikey); keys starting with AQ. are Google Cloud keys.")
    if "api key not valid" in m or "api_key_invalid" in m:
        return " Check the key in api_key.py."
    if "referer" in m or "referrer" in m or "permission_denied" in m or "403" in m:
        return (" The key may be restricted: allow your site address "
                "(https://YOURNAME.github.io/*) in the key's HTTP referrer list.")
    if "429" in m or "quota" in m or "resource_exhausted" in m:
        return " The key's free quota may be used up. Try again later."
    if "404" in m or "not found" in m:
        return " The model name may not be available for this key."
    return ""


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
    first_error = None

    for model in MODELS_TO_TRY:
        for attempt in range(2):
            try:
                text = _generate(model, key, prompt, low_thinking=(attempt == 0))
                if text:
                    return text
            except Exception as e:           # any error: try again, then the next model
                first_error = first_error or e
                if any(w in str(e).lower() for w in retry_words):
                    time.sleep(1)

    if not is_online():                      # connection dropped while we were trying
        return OFFLINE
    msg = str(first_error).rstrip(". ")
    return f"(AI explanation failed: {msg}.{_hint(msg)})"
