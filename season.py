"""When should the farmer start?  (season and month suggestions)

All the facts come from data.json (sowing_months, ok_months, duration_days,
harvest_months ...).  Nothing is hard-coded here, so improving the calendar
means editing data.json only.

Windows are typical for most of India.  Local varieties and regions differ,
so the app tells the user to confirm with the local Krishi Vigyan Kendra (KVK)
or state agriculture university.
"""
from model import DATA

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
SHORT = [m[:3] for m in MONTH_NAMES]

SEASON_LABELS = {
    "kharif": "Kharif (monsoon crop)",
    "rabi": "Rabi (winter crop)",
    "zaid": "Zaid (summer crop)",
    "year_round": "Can be grown through much of the year",
    "perennial": "Perennial (planted once, harvested for many years)",
}

CATEGORY_ORDER = ["cereal", "pulse", "oilseed", "cash crop", "vegetable", "fruit", "plantation"]


def _check_month(m):
    if not isinstance(m, int) or not 1 <= m <= 12:
        raise ValueError(f"month must be a number from 1 to 12, got {m!r}")


def format_months(months):
    """[6, 7] -> 'Jun-Jul';  [11, 12, 1] -> 'Nov-Jan';  all 12 -> 'Year-round'."""
    months = sorted(set(months))
    if not months:
        return "none"
    if len(months) == 12:
        return "Year-round"
    # a run starts at a month whose previous month is not in the set (wrapping Dec -> Jan)
    runs = []
    for m in months:
        prev = 12 if m == 1 else m - 1
        if prev not in months:
            run = [m]
            nxt = m
            while True:
                nxt = 1 if nxt == 12 else nxt + 1
                if nxt in months and nxt != m:
                    run.append(nxt)
                else:
                    break
            runs.append(run)
    parts = [SHORT[r[0] - 1] if len(r) == 1 else f"{SHORT[r[0] - 1]}-{SHORT[r[-1] - 1]}" for r in runs]
    return ", ".join(parts)


def _harvest_months(c, start_months):
    """Months in which the crop is harvested if sown in the ideal months."""
    if c.get("perennial"):
        return list(c.get("harvest_months", []))
    lag = max(1, round(c["duration_days"] / 30.4))
    return sorted({((m - 1 + lag) % 12) + 1 for m in start_months})


def rate_month(crop, month):
    """'ideal', 'ok' or 'poor' for starting `crop` in `month` (1-12)."""
    _check_month(month)
    c = DATA["crops"][crop]
    if month in c["sowing_months"]:
        return "ideal"
    if month in c["ok_months"]:
        return "ok"
    return "poor"


def months_until_ideal(crop, month):
    """How many months to wait from `month` until an ideal start month (0 = now)."""
    _check_month(month)
    ideal = DATA["crops"][crop]["sowing_months"]
    return min((m - month) % 12 for m in ideal)


def suggest_start(crop, month=None):
    """Plain-data summary the app can show.  `month` is optional (1-12)."""
    if crop not in DATA["crops"]:
        raise ValueError(f"Unknown crop '{crop}'")
    c = DATA["crops"][crop]
    ideal, ok = c["sowing_months"], c["ok_months"]
    out = {
        "crop": crop,
        "category": c["category"],
        "season": c["season"],
        "season_label": SEASON_LABELS.get(c["season"], c["season"]),
        "perennial": bool(c.get("perennial")),
        "years_to_bearing": c.get("years_to_bearing"),
        "ideal_months": list(ideal),
        "ok_months": list(ok),
        "ideal_text": format_months(ideal),
        "ok_text": format_months(ok) if ok else "",
        "harvest_text": format_months(_harvest_months(c, ideal)),
        "duration_days": c["duration_days"],
        "water_period": c.get("cycle", "season"),
        "note": c.get("note", ""),
        "rating": None,
        "advice": "",
    }
    if month is None:
        out["advice"] = f"Best time to start: {out['ideal_text']}."
        return out

    rating = rate_month(crop, month)
    wait = months_until_ideal(crop, month)
    name = MONTH_NAMES[month - 1]
    next_ideal = MONTH_NAMES[(month - 1 + wait) % 12]
    out["rating"] = rating
    if rating == "ideal":
        out["advice"] = f"{name} is an ideal month to start {crop}."
    elif rating == "ok":
        out["advice"] = (f"{name} works but is not the best month. "
                         f"The ideal time is {out['ideal_text']}"
                         f" (next: {next_ideal}, in {wait} month{'s' if wait != 1 else ''}).")
    else:
        out["advice"] = (f"{name} is a poor month to start {crop}. "
                         f"Wait for {out['ideal_text']}"
                         f" (next: {next_ideal}, in {wait} month{'s' if wait != 1 else ''}).")
    return out


def crops_for_month(month, include_ok=False):
    """Crop names that can be started in `month`, ordered by category then name."""
    _check_month(month)
    good = {"ideal", "ok"} if include_ok else {"ideal"}
    found = [k for k in DATA["crops"] if rate_month(k, month) in good]
    rank = {cat: i for i, cat in enumerate(CATEGORY_ORDER)}
    return sorted(found, key=lambda k: (rank.get(DATA["crops"][k]["category"], 99), k))


def grouped_crops_for_month(month, include_ok=False):
    """{category: [crop, ...]} for the crops that can be started in `month`."""
    groups = {}
    for k in crops_for_month(month, include_ok):
        groups.setdefault(DATA["crops"][k]["category"], []).append(k)
    return groups
