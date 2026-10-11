import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from model import DATA, Farm, run_scenario
from explain import template_explanation, ai_explanation, is_online
from season import MONTH_NAMES, suggest_start, grouped_crops_for_month
from datetime import date

st.set_page_config(page_title="FarmTwin", page_icon="🌾", layout="wide")


def pretty(x):
    """'alternate_wet_dry' -> 'Alternate wet dry', 'rice' -> 'Rice'"""
    return str(x).replace("_", " ").capitalize()


def money(v):
    return f"-₹{abs(v):,.0f}" if v < 0 else f"₹{v:,.0f}"


def explain_rows(df):
    return df.drop(columns=["Short", "Tag", "Title"]).to_dict("records")


# Simple levels -> typical numbers for the AI crop model (approximate; edit if you like)
N_LEVELS = {"Low": 30, "Medium": 70, "High": 110}
P_LEVELS = {"Low": 25, "Medium": 60, "High": 100}
K_LEVELS = {"Low": 25, "Medium": 60, "High": 110}
PH_LEVELS = {"Acidic": 5.5, "Neutral": 6.8, "Alkaline": 8.0}

# (column, label, lower_is_better, formatter)
METRICS = [
    ("Water use (m³)", "Water use", True, lambda v: f"{v:,.0f} m³"),
    ("Cultivation cost (₹)", "Cultivation cost", True, money),
    ("Yield (kg)", "Yield", False, lambda v: f"{v:,.0f} kg"),
    ("Net returns (₹)", "Net returns", False, money),
]

# (column, badge text, lower_is_better)  -- listed in priority order
AWARDS = [
    ("Net returns (₹)", "Highest net returns", False),
    ("Water use (m³)", "Least water", True),
    ("Yield (kg)", "Highest yield", False),
    ("Cultivation cost (₹)", "Lowest cost", True),
]

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
.block-container { padding-top: 2rem; max-width: 1200px; }

/* ---------- shared animations ---------- */
@keyframes fadeUp { from { opacity: 0; transform: translateY(18px); }
                    to   { opacity: 1; transform: translateY(0); } }
@keyframes glow { 0%, 100% { box-shadow: 0 0 0 0 rgba(197,229,92,.35); }
                  50%      { box-shadow: 0 0 0 14px rgba(197,229,92,0); } }

/* ---------- front page ---------- */
.landing { padding: 16vh 0 4vh; text-align: center; }
.landing.entered { padding: 2vh 0 0; text-align: left; }
.landing.entered h1 { color: #C5E55C; }
.tagline { font-size: 1.25rem; line-height: 1.7; opacity: .85; max-width: 800px; margin: 1.6rem 0 1.2rem; }
.chips { display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 2rem; }
.chip { border: 1px solid #C5E55C; color: #C5E55C; border-radius: 999px;
        padding: 6px 18px; font-size: 1rem; }
.landing h1 { font-size: clamp(4rem, 14vw, 10rem); font-weight: 700; line-height: 0.95;
              letter-spacing: -0.04em; margin: 0; animation: fadeUp .9s ease both; }
.landing h1 span { color: #C5E55C; }

/* the big "Enter" button (only normal primary button on the page) */
[data-testid="stBaseButton-primary"], button[kind="primary"] {
    width: 100%; background: #C5E55C; border: none; border-radius: 999px;
    padding: .9rem 1.5rem;
    animation: fadeUp 1s ease .3s both, glow 2.4s ease-in-out 1.4s infinite;
    transition: transform .15s ease, background .15s ease; }
[data-testid="stBaseButton-primary"] p, button[kind="primary"] p {
    color: #0F3A2E !important; font-weight: 700; font-size: 1.2rem; }
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover {
    background: #d8f07a; transform: translateY(-3px); }

/* ---------- section titles ---------- */
.section { font-size: .8rem; letter-spacing: .12em; text-transform: uppercase;
           color: #C5E55C; margin: 1.2rem 0 .4rem; font-weight: 700;
           animation: fadeUp .6s ease both; }

/* ---------- form (fades in after Enter) + run button ---------- */
[data-testid="stForm"] { border: 1px solid rgba(197,229,92,.3); border-radius: 18px;
                         padding: 1.5rem; background: transparent;
                         animation: fadeUp .8s ease both; }
[data-testid="stExpander"] { border: 1px solid rgba(197,229,92,.25) !important;
                             border-radius: 14px; margin-top: .8rem; }
[data-testid="stFormSubmitButton"] button { background: #C5E55C; color: #0F3A2E;
        font-weight: 700; border: none; border-radius: 999px;
        padding: .6rem 2.4rem; font-size: 1.05rem; animation: none;
        transition: transform .15s ease, box-shadow .15s ease; }
[data-testid="stFormSubmitButton"] button p { color: #0F3A2E !important; font-size: 1.05rem; }
[data-testid="stFormSubmitButton"] button:hover { background: #d8f07a; color: #0F3A2E;
        transform: translateY(-2px); box-shadow: 0 8px 20px rgba(197,229,92,.25); }

/* ---------- explanation box ---------- */
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 18px !important;
        border-color: rgba(197,229,92,.3) !important; }

/* ---------- dropdown animations ---------- */
@keyframes dropIn {
  from { opacity: 0; transform: translateY(-10px) scale(.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
div[data-baseweb="select"] > div { transition: border-color .2s ease, box-shadow .2s ease; }
div[data-baseweb="select"] > div:hover { border-color: #C5E55C !important;
        box-shadow: 0 0 0 3px rgba(197,229,92,.18); }
div[data-baseweb="select"] svg { transition: transform .25s ease; }
div[data-baseweb="select"]:focus-within svg { transform: rotate(180deg); }
div[data-baseweb="popover"] > div { animation: dropIn .22s ease-out; transform-origin: top center;
        border-radius: 14px !important; overflow: hidden; }
li[role="option"] { transition: background .15s ease, padding-left .15s ease; }
li[role="option"]:hover { background: rgba(197,229,92,.18) !important; padding-left: 1.5rem; }

/* ---------- simple cards (AI recommendation) ---------- */
.card { background: #1A1D26; border: 1px solid rgba(197,229,92,.25);
        border-radius: 18px; padding: 20px; height: 100%;
        animation: fadeUp .5s ease both; transition: transform .2s ease, box-shadow .2s ease; }
.card:hover { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(0,0,0,.3); }
.card h4 { margin: 0 0 14px 0; font-size: 1rem; line-height: 1.3; }
.big { font-size: 2.4rem; font-weight: 700; color: #C5E55C; line-height: 1.1; }

/* ---------- comparison cards ---------- */
.cmp-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: .5rem 0 1rem; }
@media (max-width: 900px) { .cmp-grid { grid-template-columns: 1fr; } }
.cmp-card { background: #1A1D26; border: 1px solid rgba(197,229,92,.25); border-radius: 20px;
            padding: 22px 24px; animation: fadeUp .5s ease both;
            transition: transform .2s ease, box-shadow .2s ease; }
.cmp-card:hover { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(0,0,0,.3); }
.cmp-card.top { border: 2px solid #C5E55C; }
.cmp-badges { min-height: 30px; display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.cmp-badge { background: #C5E55C; color: #0F3A2E; border-radius: 999px;
             padding: 4px 12px; font-size: .74rem; font-weight: 700; }
.cmp-tag { font-size: .78rem; letter-spacing: .12em; text-transform: uppercase;
           color: #C5E55C; font-weight: 700; margin-bottom: 4px; }
.cmp-title { font-size: 1.15rem; font-weight: 700; padding-bottom: 14px;
             border-bottom: 1px solid rgba(255,255,255,.12); }
.cmp-row { padding: 14px 0; border-bottom: 1px solid rgba(255,255,255,.08); }
.cmp-row:last-child { border-bottom: none; padding-bottom: 2px; }
.cmp-label { font-size: .82rem; opacity: .7; }
.cmp-value { font-size: 1.9rem; font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; }
.cmp-delta { font-size: .85rem; font-weight: 500; }
.cmp-delta.good { color: #C5E55C; }
.cmp-delta.bad { color: #FF8A7A; }
.cmp-delta.flat { opacity: .65; }

/* ---------- explanation focus (trade-offs vs AI) ---------- */
@keyframes popIn { 0% { opacity: 0; transform: translateY(14px) scale(.96); }
                   60% { opacity: 1; transform: translateY(-3px) scale(1.01); }
                   100% { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes aiGlow { 0%, 100% { box-shadow: 0 0 0 1px rgba(197,229,92,.5), 0 10px 40px rgba(197,229,92,.18); }
                    50%      { box-shadow: 0 0 0 1px rgba(197,229,92,.9), 0 14px 56px rgba(197,229,92,.34); } }
.st-key-tradeoffs_focus { border: 2px solid #C5E55C !important; border-radius: 18px !important;
        background: rgba(197,229,92,.04); animation: popIn .5s ease both;
        box-shadow: 0 0 0 4px rgba(197,229,92,.10), 0 12px 40px rgba(197,229,92,.15); }
.st-key-tradeoffs_dim { opacity: .5; filter: saturate(.7); transition: opacity .3s ease, filter .3s ease; }
.st-key-tradeoffs_dim:hover { opacity: 1; filter: none; }
.st-key-ai_box { border: 2px solid #C5E55C !important; border-radius: 20px !important;
        padding: 1.2rem 1.4rem !important; margin-bottom: 1.2rem;
        background: linear-gradient(135deg, rgba(197,229,92,.12), rgba(197,229,92,.02));
        animation: popIn .6s cubic-bezier(.2,.9,.3,1.2) both, aiGlow 3s ease-in-out .7s infinite; }
.ai-head { display: inline-block; background: #C5E55C; color: #0E1117; font-weight: 700;
        font-size: .8rem; letter-spacing: .1em; text-transform: uppercase;
        border-radius: 999px; padding: 4px 14px; margin-bottom: .6rem; }

/* ---------- "crops you can start" card ---------- */
.start-card { background: #1A1D26; border: 1px solid rgba(197,229,92,.25); border-radius: 20px;
        padding: 28px 32px; margin: 1rem 0; animation: fadeUp .5s ease both; }
.start-title { font-size: 1.9rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.2; }
.start-title span { color: #C5E55C; }
.start-sub { font-size: .95rem; opacity: .65; margin: 4px 0 20px; }
.start-label { font-size: .85rem; letter-spacing: .12em; text-transform: uppercase; font-weight: 700;
        color: #C5E55C; margin: 18px 0 8px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,.10); }
.start-label.first { border-top: none; padding-top: 0; margin-top: 0; }
.start-label.ok { color: #E6C65C; }
.start-row { display: flex; align-items: baseline; gap: 18px; padding: 10px 0; }
.start-cat { min-width: 130px; font-size: 1.05rem; font-weight: 700; opacity: .9; }
.start-chips { display: flex; flex-wrap: wrap; gap: 10px; }
.crop-chip { border-radius: 999px; padding: 7px 18px; font-size: 1.1rem; font-weight: 500;
        transition: transform .15s ease; }
.crop-chip:hover { transform: translateY(-2px); }
.crop-chip.ideal { background: #C5E55C; color: #0E1117; font-weight: 700; }
.crop-chip.ok { border: 1px solid rgba(255,255,255,.28); color: #E6E8EC; }
.start-empty { font-size: 1.05rem; opacity: .7; }
@media (max-width: 700px) { .start-row { flex-direction: column; gap: 6px; } }
</style>
""", unsafe_allow_html=True)

if st.session_state.get("entered", False):
    st.markdown(
        '<div class="landing entered"><h1>FarmTwin</h1>'
        '<div class="tagline">Intelligent solutions for sustainable agriculture. '
        'Test crop and irrigation choices on a virtual farm before you commit.</div>'
        '<div class="chips"><span class="chip">✓ Digital twin</span>'
        '<span class="chip">✓ What-if scenarios</span>'
        '<span class="chip">✓ AI crop recommendation</span>'
        '<span class="chip">✓ Explainable results</span></div></div>',
        unsafe_allow_html=True)
else:
    st.markdown('<div class="landing"><h1>Farm<span>Twin</span></h1></div>',
                unsafe_allow_html=True)

# ---------------- FRONT PAGE ----------------
if "entered" not in st.session_state:
    st.session_state["entered"] = False

if not st.session_state["entered"]:
    _, mid, _ = st.columns([3, 2, 3])
    if mid.button("Enter FarmTwin  →", type="primary"):
        st.session_state["entered"] = True
        st.session_state["just_entered"] = True
        st.rerun()
    st.markdown('<div style="height:16vh"></div>', unsafe_allow_html=True)
    st.stop()   # nothing else is shown until the button is pressed

# ---------------- AFTER ENTERING ----------------
st.markdown('<div style="height:4vh"></div><div id="farm-form-anchor"></div>',
            unsafe_allow_html=True)

if st.session_state.pop("just_entered", False):
    try:   # gentle scroll down to the form (skipped silently if the browser blocks it)
        components.html(
            "<script>setTimeout(function(){"
            "var a = window.parent.document.getElementById('farm-form-anchor');"
            "if (a) { a.scrollIntoView({behavior: 'smooth', block: 'start'}); }"
            "}, 350);</script>", height=0)
    except Exception:
        pass

crops = list(DATA["crops"].keys())
methods = list(DATA["irrigation"].keys())

# ---------------- INPUTS (horizontal) + RUN BUTTON ----------------
with st.form("inputs"):
    st.markdown('<div class="section">1 · Your farm</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    size = c1.number_input("Farm size (ha)", 0.5, 100.0, 2.0, step=0.5)
    soil = c2.selectbox("Soil type", list(DATA["soil"].keys()), format_func=pretty)
    crop = c3.selectbox("Crop", crops, format_func=pretty)
    rain = c4.number_input("Seasonal rainfall (mm)", 0, 3000, 900, step=50)
    irrigation = c5.selectbox("Irrigation method", methods, format_func=pretty)

    st.markdown('<div class="section">2 · Scenarios to compare</div>', unsafe_allow_html=True)
    d1, d2, d3, d4 = st.columns(4)
    limit = d1.checkbox("Limit irrigation water?")
    max_irr_input = d1.number_input("Max irrigation (mm)", 0, 1500, 500, step=50)
    alt_irr = d2.selectbox("Scenario 1: switch irrigation to", methods, format_func=pretty,
                           index=methods.index("drip") if "drip" in methods else 0)
    alt_crop = d3.selectbox("Scenario 2: switch crop to", crops, format_func=pretty,
                            index=min(2, len(crops) - 1))
    rain_change = d4.slider("Scenario 2: rainfall change (%)", -50, 50, 0, step=10)

    st.markdown('<div class="section">3 · When do you plan to start?</div>', unsafe_allow_html=True)
    start_choice = st.selectbox("Planned start month (optional)", ["Not decided"] + MONTH_NAMES)

    # ----- OPTIONAL: soil & weather for the AI crop model -----
    with st.expander("4 · Soil & weather details (optional, for the AI crop recommendation)"):
        st.caption("Skip this if you don't have a soil test or Soil Health Card. "
                   "The simulation above works without it.")
        use_soil = st.checkbox("Include these details in the AI crop recommendation")
        e1, e2, e3, e4, e5, e6 = st.columns(6)
        n_level = e1.selectbox("Nitrogen level", list(N_LEVELS), index=1)
        p_level = e2.selectbox("Phosphorus level", list(P_LEVELS), index=1)
        k_level = e3.selectbox("Potassium level", list(K_LEVELS), index=1)
        ph_level = e4.selectbox("Soil pH", list(PH_LEVELS), index=1)
        temp = e5.number_input("Temperature (°C)", 8.0, 44.0, 26.0, step=0.5)
        hum = e6.number_input("Humidity (%)", 14.0, 100.0, 80.0, step=1.0)

    auto_ai = st.checkbox("✨ Write the AI explanation automatically when I run "
                          "(takes a few extra seconds)")
    run = st.form_submit_button("▶  Run simulation", type="primary")

# ---------------- RUN ----------------
if run:
    max_irr = max_irr_input if limit else 99999
    farm = Farm(size_ha=size, soil_type=soil, crop=crop, rainfall_mm=rain,
                irrigation=irrigation, max_irrigation_mm=max_irr)

    scenarios = [
        ("Baseline", "Baseline", f"{pretty(crop)}, {pretty(irrigation)}", {}),
        ("Irrigation", "Scenario 1",
         f"Irrigation: {pretty(crop)}, {pretty(alt_irr)}", {"irrigation": alt_irr}),
        ("Alternative", "Scenario 2",
         f"Alternative: {pretty(alt_crop)}, {rain_change:+d}% rain",
         {"crop": alt_crop, "rainfall_mm": rain * (1 + rain_change / 100)}),
    ]
    rows = []
    for short, tag, title, changes in scenarios:
        r = run_scenario(farm, **changes)
        rows.append({
            "Scenario": f"{tag} · {title}",
            "Tag": tag,
            "Title": title,
            "Short": short,
            "Water use (m³)": r["water_use_m3"],
            "Cultivation cost (₹)": r["cost"],
            "Yield (kg)": r["yield_kg"],
            "Net returns (₹)": r["net_returns"],
        })
    df = pd.DataFrame(rows)

    recs, rec_note = None, None
    if not use_soil:
        rec_note = ("AI crop recommendation skipped. Open the optional soil & weather "
                    "section, tick the box, and run again to get it.")
    else:
        try:
            from recommend import top_crops
            recs = top_crops(N_LEVELS[n_level], P_LEVELS[p_level], K_LEVELS[k_level],
                             temp, hum, PH_LEVELS[ph_level], rain / 4)  # seasonal rain -> approx monthly
        except FileNotFoundError:
            rec_note = ("The crop model files (crop_model.joblib or Crop_recommendation.csv) "
                        "are missing from this build.")
        except Exception as e:
            rec_note = f"Recommendation unavailable: {e}"

    summary = f"{size} ha, {soil} soil, {rain} mm rainfall"
    if recs:
        summary += f"; the ML model suggests {recs[0][0]} for the soil and weather conditions given"

    # ----- when to start farming -----
    month_num = MONTH_NAMES.index(start_choice) + 1 if start_choice != "Not decided" else None
    timing = [("Your crop", suggest_start(crop, month_num))]
    if alt_crop != crop:
        timing.append(("Scenario 2 crop", suggest_start(alt_crop, month_num)))
    if recs and recs[0][0] in DATA["crops"] and recs[0][0] not in (crop, alt_crop):
        timing.append(("AI suggestion", suggest_start(recs[0][0], month_num)))
    look_month = month_num or date.today().month
    start_now = {"month": look_month, "chosen": month_num is not None,
                 "ideal": grouped_crops_for_month(look_month),
                 "ok": grouped_crops_for_month(look_month, include_ok=True)}

    st.session_state["res"] = {"df": df, "recs": recs, "rec_note": rec_note, "summary": summary,
                               "timing": timing, "start_now": start_now}
    st.session_state.pop("ai_text", None)

    if auto_ai:
        with st.spinner("Writing the AI explanation..."):
            st.session_state["ai_text"] = ai_explanation(explain_rows(df), summary) or "__none__"


# ---------------- COMPARISON CARDS ----------------
def build_comparison(df):
    base = df.iloc[0]

    # awards: only given when there is a single clear winner
    awards = {i: [] for i in range(len(df))}
    for col, text, lower in AWARDS:
        target = df[col].min() if lower else df[col].max()
        winners = df.index[df[col] == target].tolist()
        if len(winners) == 1:
            awards[winners[0]].append(text)

    top_idx = df["Net returns (₹)"].idxmax()
    cards = []
    for i, row in df.iterrows():
        badges = "".join(f'<span class="cmp-badge">{t}</span>' for t in awards[i][:2])
        parts = [f'<div class="cmp-card{" top" if i == top_idx else ""}">',
                 f'<div class="cmp-badges">{badges}</div>',
                 f'<div class="cmp-tag">{row["Tag"]}</div>',
                 f'<div class="cmp-title">{row["Title"]}</div>']
        for col, label, lower, fmt in METRICS:
            value = row[col]
            if i == 0:
                cls, text = "flat", "Starting point"
            else:
                d = value - base[col]
                if d == 0:
                    cls, text = "flat", "No change"
                else:
                    arrow = "▲" if d > 0 else "▼"
                    better = (d < 0) if lower else (d > 0)
                    cls = "good" if better else "bad"
                    text = f"{arrow} {fmt(abs(d))} vs baseline"
            parts.append(
                f'<div class="cmp-row"><div class="cmp-label">{label}</div>'
                f'<div class="cmp-value">{fmt(value)}</div>'
                f'<div class="cmp-delta {cls}">{text}</div></div>')
        parts.append('</div>')
        cards.append("".join(parts))
    return '<div class="cmp-grid">' + "".join(cards) + '</div>'


# ---------------- CHART HELPER ----------------
def make_chart(df, metric, lower_is_better):
    vals = df[metric].tolist()
    best_val = min(vals) if lower_is_better else max(vals)
    colors = ["#C5E55C" if v == best_val else "#3A3F4B" for v in vals]
    hint = "lower is better" if lower_is_better else "higher is better"

    fig = go.Figure(go.Bar(
        x=df["Short"], y=vals, marker_color=colors,
        text=[f"{v:,.0f}" for v in vals], textposition="outside", cliponaxis=False,
        textfont=dict(size=15, color="#E6E8EC"),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>",
    ))
    try:
        fig.update_traces(marker_cornerradius=10)   # rounded bars (newer Plotly only)
    except Exception:
        pass
    top = max(vals) if max(vals) > 0 else 1
    fig.update_layout(
        title=dict(text=f"<b>{metric}</b><br><sup>{hint} · lime = best</sup>", x=0.02),
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Space Grotesk, sans-serif", size=14),
        margin=dict(t=85, b=20, l=10, r=10), height=350, bargap=0.45, showlegend=False,
        xaxis=dict(title=None, showgrid=False, showline=False),
        yaxis=dict(visible=False, range=[0, top * 1.3]),
        hoverlabel=dict(bgcolor="#1A1D26", font_size=14),
    )
    return fig


# ---------------- RESULTS ----------------
res = st.session_state.get("res")

if not res:
    st.info("Fill in the details above and press **Run simulation**.")
else:
    df = res["df"]

    # --- 1. Explanation ---
    if st.session_state.pop("ai_requested", False):
        with st.spinner("Thinking..."):
            st.session_state["ai_text"] = ai_explanation(explain_rows(df), res["summary"]) or "__none__"
        st.session_state["ai_scroll"] = True
    ai_text = st.session_state.get("ai_text")
    has_ai = bool(ai_text) and ai_text not in ("__none__", "__offline__")

    st.markdown('<div class="section">Explain the trade-offs</div>', unsafe_allow_html=True)

    # AI explanation goes first (top) and pops out once it exists
    if has_ai:
        with st.container(border=True, key="ai_box"):
            st.markdown('<span class="ai-head">✨ AI explanation</span>', unsafe_allow_html=True)
            st.write(ai_text)
        if st.session_state.pop("ai_scroll", False):
            try:   # gently bring the AI box into view
                components.html(
                    "<script>setTimeout(function(){"
                    "var a = window.parent.document.querySelector('.st-key-ai_box');"
                    "if (a) { a.scrollIntoView({behavior: 'smooth', block: 'center'}); }"
                    "}, 300);</script>", height=0)
            except Exception:
                pass

    # trade-offs box: highlighted until the AI text exists, then it fades back below it
    with st.container(border=True, key="tradeoffs_dim" if has_ai else "tradeoffs_focus"):
        st.markdown(template_explanation(explain_rows(df)))

        st.button("✨ Regenerate AI explanation" if has_ai else "✨ Get AI explanation",
                  on_click=lambda: st.session_state.update(ai_requested=True))

        if ai_text == "__none__":
            st.info("No API key set, so only the built-in explanation is shown.")
        elif ai_text == "__offline__":
            st.warning("📴 You're offline, so only the built-in explanation is shown. "
                       "The AI explanation works again as soon as you're connected.")
        elif not is_online():
            st.caption("📴 Offline: everything works except the AI explanation, "
                       "which needs an internet connection.")

    # --- 2. AI crop recommendation (optional) ---
    st.markdown('<div class="section">AI crop recommendation</div>', unsafe_allow_html=True)
    if res["recs"]:
        rec_cols = st.columns(len(res["recs"]))
        for col, (name, prob) in zip(rec_cols, res["recs"]):
            tag = "can be simulated" if name in crops else "not in the simulator"
            col.markdown(
                f'<div class="card"><h4>{pretty(name)}</h4>'
                f'<div class="big">{prob * 100:.0f}%</div><small>{tag}</small></div>',
                unsafe_allow_html=True)
        st.caption("Random Forest trained on the Crop Recommendation dataset, using the soil levels "
                   "you selected (converted to typical values, so treat this as a rough suggestion). "
                   "The simulation shows each crop's water, cost, yield and returns.")
    else:
        st.info(res["rec_note"])

    # --- 2b. When to start farming ---
    if res.get("timing"):
        st.markdown('<div class="section">When to start farming</div>', unsafe_allow_html=True)
        timing_cols = st.columns(len(res["timing"]))
        badges = {"ideal": "✅ Ideal month", "ok": "⚠️ Workable, not ideal", "poor": "❌ Poor month"}
        for col, (role, t) in zip(timing_cols, res["timing"]):
            extra = ""
            if t["perennial"] and t["years_to_bearing"]:
                extra += f"Bears fruit from year {t['years_to_bearing']}.<br>"
            if t["water_period"] == "year":
                extra += "Use yearly rainfall for this crop.<br>"
            badge = badges.get(t["rating"], "")
            col.markdown(
                f'<div class="card"><h4>{role}: {pretty(t["crop"])}</h4>'
                f'<div class="big">{t["ideal_text"]}</div>'
                f'<small>{t["season_label"]}<br>Harvest: {t["harvest_text"]}<br>{extra}</small>'
                f'<p><b>{badge}</b></p></div>',
                unsafe_allow_html=True)
            if t["rating"]:
                col.caption(t["advice"])

        sn = res["start_now"]
        which = "your planned month" if sn["chosen"] else "this month"
        month_name = MONTH_NAMES[sn["month"] - 1]

        def crop_chips(items, cls):
            return "".join(f'<span class="crop-chip {cls}">{pretty(k)}</span>' for k in items)

        def rows_html(groups, cls):
            return "".join(
                f'<div class="start-row"><div class="start-cat">{cat.title()}</div>'
                f'<div class="start-chips">{crop_chips(ks, cls)}</div></div>'
                for cat, ks in groups.items())

        also = {}
        for cat, ks in sn["ok"].items():
            rest = [k for k in ks if k not in sn["ideal"].get(cat, [])]
            if rest:
                also[cat] = rest

        html = (f'<div class="start-card">'
                f'<div class="start-title">Crops you can start in <span>{month_name}</span></div>'
                f'<div class="start-sub">{which}</div>'
                f'<div class="start-label first">✅ Ideal</div>')
        html += (rows_html(sn["ideal"], "ideal") if sn["ideal"] else
                 '<div class="start-empty">No crop in the list has this as its ideal month.</div>')
        if also:
            html += '<div class="start-label ok">⚠️ Workable, not ideal</div>' + rows_html(also, "ok")
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Sowing windows are typical for most of India. Local weather, variety and region "
                   "change them, so confirm with your local Krishi Vigyan Kendra (KVK) or state "
                   "agriculture university before sowing.")

    # --- 3. Scenario comparison ---
    st.markdown('<div class="section">Scenario comparison</div>', unsafe_allow_html=True)
    st.markdown(build_comparison(df), unsafe_allow_html=True)

    # --- 4. Charts ---
    st.markdown('<div class="section">Comparison charts</div>', unsafe_allow_html=True)
    chart_specs = [
        ("Water use (m³)", True),
        ("Cultivation cost (₹)", True),
        ("Yield (kg)", False),
        ("Net returns (₹)", False),
    ]
    left, right = st.columns(2)
    for i, (metric, lower) in enumerate(chart_specs):
        target = left if i % 2 == 0 else right
        fig = make_chart(df, metric, lower)
        try:
            target.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        except TypeError:   # older Streamlit versions
            target.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with st.expander("Assumptions used"):
        st.write("Only 75% of rainfall is counted as useful. Parameters come from the sources listed below; items marked as assumptions are team estimates. "
                 "Fruit and vegetable results use estimated prices and leave out price swings, spoilage, labour and, for orchards, "
                 "the years before the first harvest, so treat them as rough comparisons.")
        st.json(DATA)

st.caption("FarmTwin · Academic project · Anirudh R Sharma & Shreyan Venkat")

if st.button("↑ Back to start"):
    st.session_state["entered"] = False
    st.rerun()