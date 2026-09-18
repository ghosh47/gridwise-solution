import pulp
from typing import List, Tuple
from app.schemas import HourInput, BatteryInput, DirectiveInterpretation, HourlyPlanItem

def solve_grid_optimization(
    hours: List[HourInput],
    battery: BatteryInput,
    directives: List[DirectiveInterpretation]
) -> Tuple[List[HourlyPlanItem], float, float, float]:
    
    # সোলার অ্যাডজাস্টমেন্ট
    solar_avail = [h.solar_kwh for h in hours]
    for d in directives:
        if d.applies and d.directive_type == "solar_reduction" and d.structured_adjustment:
            factor = d.structured_adjustment.factor if d.structured_adjustment.factor is not None else 1.0
            for hr in (d.structured_adjustment.hours or []):
                solar_avail[hr] = solar_avail[hr] * factor

    # কনস্ট্রেইন্ট উইন্ডো ফিল্টার
    no_charge_hrs = set()
    no_discharge_hrs = set()
    min_reserve = {t: battery.minimum_energy_kwh for t in range(24)}
    max_grid = {t: None for t in range(24)}

    for d in directives:
        if not d.applies or not d.structured_adjustment:
            continue
        hrs = d.structured_adjustment.hours or []
        if d.directive_type == "no_charge_window":
            no_charge_hrs.update(hrs)
        elif d.directive_type == "no_discharge_window":
            no_discharge_hrs.update(hrs)
        elif d.directive_type == "minimum_battery_reserve":
            for hr in hrs:
                min_reserve[hr] = max(min_reserve[hr], d.structured_adjustment.minimum_energy_kwh)
        elif d.directive_type == "max_grid_window":
            for hr in hrs:
                max_grid[hr] = d.structured_adjustment.max_grid_kwh

    # LP সমস্যা গঠন
    prob = pulp.LpProblem("GridWise_LP", pulp.LpMinimize)

    grid = [pulp.LpVariable(f"grid_{t}", lowBound=0) for t in range(24)]
    solar_used = [pulp.LpVariable(f"solar_used_{t}", lowBound=0, upBound=solar_avail[t]) for t in range(24)]
    charge = [pulp.LpVariable(f"charge_{t}", lowBound=0, upBound=battery.max_charge_kwh_per_hour) for t in range(24)]
    discharge = [pulp.LpVariable(f"discharge_{t}", lowBound=0, upBound=battery.max_discharge_kwh_per_hour) for t in range(24)]
    soc = [pulp.LpVariable(f"soc_{t}", lowBound=0, upBound=battery.capacity_kwh) for t in range(24)]

    # খরচ মিনিমাইজ করার অবজেক্টিভ
    prob += pulp.lpSum([grid[t] * hours[t].tariff_bdt_per_kwh for t in range(24)])

    prev_soc = battery.initial_energy_kwh
    for t in range(24):
        # এনার্জি ব্যালান্স
        prob += grid[t] + solar_used[t] + discharge[t] == hours[t].demand_kwh + charge[t]
        # ব্যাটারি সঞ্চয় হিসাব
        prob += soc[t] == prev_soc + charge[t] - discharge[t]
        prev_soc = soc[t]
        prob += soc[t] >= min_reserve[t]

        if t in no_charge_hrs:
            prob += charge[t] == 0
        if t in no_discharge_hrs:
            prob += discharge[t] == 0
        if max_grid[t] is not None:
            prob += grid[t] <= max_grid[t]

    # দিন শেষে ব্যাটারি নিউট্রালিটি
    prob += soc[23] == battery.initial_energy_kwh

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    hourly_plan = []
    for t in range(24):
        c_val = float(charge[t].varValue or 0.0)
        d_val = float(discharge[t].varValue or 0.0)

        if c_val > 0.001:
            action = "charge"
            b_kwh = c_val
        elif d_val > 0.001:
            action = "discharge"
            b_kwh = d_val
        else:
            action = "idle"
            b_kwh = 0.0

        hourly_plan.append(HourlyPlanItem(
            hour=t,
            grid_kwh=round(float(grid[t].varValue or 0.0), 2),
            solar_used_kwh=round(float(solar_used[t].varValue or 0.0), 2),
            battery_action=action,
            battery_kwh=round(b_kwh, 2),
            battery_energy_after_kwh=round(float(soc[t].varValue or 0.0), 2)
        ))

    total_grid_kwh = round(sum(p.grid_kwh for p in hourly_plan), 2)
    total_cost_bdt = round(sum(p.grid_kwh * hours[t].tariff_bdt_per_kwh for t, p in enumerate(hourly_plan)), 2)
    peak_grid_kwh = round(max(p.grid_kwh for p in hourly_plan), 2)

    return hourly_plan, total_grid_kwh, total_cost_bdt, peak_grid_kwh