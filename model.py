import json
from dataclasses import dataclass, replace
from pathlib import Path

def _load_data():
    """data.json sits next to this file on a PC, or in the working folder in the browser build."""
    for p in (Path(__file__).parent / "data.json", Path("data.json")):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            continue
    raise FileNotFoundError("data.json not found")


DATA = _load_data()


@dataclass
class Farm:
    size_ha: float
    soil_type: str
    crop: str
    rainfall_mm: float
    irrigation: str                    # "flood", "alternate_wet_dry", or "drip"
    max_irrigation_mm: float = 99999   # water available; default = unlimited
    def __post_init__(self):
        if self.size_ha < 0:
            raise ValueError("size_ha cannot be negative")
        if self.rainfall_mm < 0:
            raise ValueError("rainfall_mm cannot be negative")
        if self.max_irrigation_mm < 0:
            raise ValueError("max_irrigation_mm cannot be negative")
        if self.soil_type not in DATA["soil"]:
            raise ValueError(f"Unknown soil '{self.soil_type}'. Options: {list(DATA['soil'])}")
        if self.crop not in DATA["crops"]:
            raise ValueError(f"Unknown crop '{self.crop}'. Options: {list(DATA['crops'])}")
        if self.irrigation not in DATA["irrigation"]:
            raise ValueError(f"Unknown irrigation '{self.irrigation}'. Options: {list(DATA['irrigation'])}")

def simulate(farm: Farm) -> dict:
    
    crop = DATA["crops"][farm.crop]
    irr = DATA["irrigation"][farm.irrigation]

        # 1. Water the crop gets from rain (75% of rain is useful, scaled by how well the soil holds it)
    effective_rain = 0.75 * farm.rainfall_mm * DATA["soil"][farm.soil_type]["rain_factor"]

    # 2. Extra water the crop needs on top of rain
    net_need = max(0, crop["water_req_mm"] - effective_rain)

    # 3. Water we must pump/apply, since some is lost (efficiency)
    gross_irrigation = net_need / irr["efficiency"]
    gross_irrigation = min(gross_irrigation, farm.max_irrigation_mm)

    # 4. Water that actually reaches the crop
    delivered = gross_irrigation * irr["efficiency"]
    supplied = effective_rain + delivered

    # 5. Water stress -> yield loss
    
    stress_ratio = min(1, supplied / crop["water_req_mm"])
    yield_per_ha = crop["base_yield_kg_ha"] * (1 - crop["sensitivity"] * (1 - stress_ratio))
    yield_per_ha = max(0, yield_per_ha)
    
    # 6. Totals for the whole farm
    total_yield = yield_per_ha * farm.size_ha
    water_use_m3 = gross_irrigation * 10 * farm.size_ha   # 1 mm on 1 ha = 10 m3
    irrigation_cost = (gross_irrigation * irr["cost_per_mm_ha"] + irr["fixed_cost_per_ha"]) * farm.size_ha
    total_cost = crop["other_cost_per_ha"] * farm.size_ha + irrigation_cost
    revenue = total_yield * crop["price_per_kg"]

    return {
        "water_use_m3": round(water_use_m3),
        "cost": round(total_cost),
        "yield_kg": round(total_yield),
        "net_returns": round(revenue - total_cost),
    }


def run_scenario(farm: Farm, **changes) -> dict:
    """Copy the farm, apply the changes, and simulate."""
    return simulate(replace(farm, **changes))


if __name__ == "__main__":
    farm = Farm(size_ha=2, soil_type="clay", crop="rice",
                rainfall_mm=900, irrigation="flood")

    scenarios = {
        "Baseline (rice, flood)": {},
        "Irrigation change (rice, drip)": {"irrigation": "drip"},
        "Alternative crop (millet)": {"crop": "millet"},
    }

    for name, changes in scenarios.items():
        print(name, "->", run_scenario(farm, **changes))