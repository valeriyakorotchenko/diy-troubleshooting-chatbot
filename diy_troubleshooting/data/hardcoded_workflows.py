from diy_troubleshooting.domain.models import Workflow, Step, Option

# ==============================================================================
# STEP DEFINITIONS
# ==============================================================================

# --- STEP 1: THERMOSTAT (From Section: "Check and Adjust the Thermostat") ---
step_01 = Step(
    id="step_01_thermostat",
    type="ask_choice",
    goal="Instruct user to check the thermostat dial. Determine if adjusting it fixes the issue.",
    background_context=(
        "The thermostat is on the hot water tank. It can get bumped accidently. "
        "If it is too low, the water will be lukewarm."
    ),
    warning="Do not set the temperature above 120°F (scalding risk).",
    options=[
        Option(
            id="was_low",
            label="The thermostat was set too low. User adjusted it and the issue is now resolved.",
            next_step_id="end_success_thermostat"
        ),
        Option(
            id="was_correct",
            label="The thermostat was already set correctly, or adjusting it did not resolve the issue.",
            next_step_id="step_02_breaker"
        ),
    ]
)

# --- STEP 2: BREAKER (From Section: "Tripped Hot Water Tank Breaker") ---
step_02 = Step(
    id="step_02_breaker",
    type="ask_choice",
    goal="Check if the circuit breaker is tripped.",
    background_context=(
        "Electric tanks need power. Power surges can trip the breaker. "
        "If water stays lukewarm for >24h, it's likely NOT the breaker (since it's heating partially)."
    ),
    options=[
        Option(
            id="tripped",
            label="The circuit breaker was found in a tripped state.",
            next_step_id="step_02a_reset_breaker"
        ),
        Option(
            id="not_tripped",
            label="The circuit breaker is in the ON position and functioning normally.",
            next_step_id="step_03_demand"
        ),
    ]
)

# --- STEP 2a: RESET BREAKER INSTRUCTION ---
step_02a = Step(
    id="step_02a_reset_breaker",
    type="instruction",
    goal="Guide user to reset the breaker and test.",
    background_context="Flip to OFF, then firmly back to ON. Wait an hour or so to see if the water heats up. If it trips again immediately, you have an electrical short.",
    next_step="end_monitor"
)

# --- STEP 3: HIGH DEMAND (From Section: "Unmanageable Hot Water Demand") ---
step_03 = Step(
    id="step_03_demand",
    type="ask_choice",
    goal="Determine if the household simply used up all the hot water temporarily.",
    background_context=(
        "Running laundry, dishwasher, and showers simultaneously depletes the tank. "
        "Recovery takes time."
    ),
    options=[
        Option(
            id="heavy_use",
            label="The household experienced high hot water demand recently (multiple appliances or showers running).",
            next_step_id="end_wait_recovery"
        ),
        Option(
            id="normal_use",
            label="Hot water usage has been within normal patterns with no unusual demand.",
            next_step_id="step_04_leak"
        ),
    ]
)

# --- STEP 4: LEAK CHECK (From Section: "Leaking Hot Water Tank") ---
step_04 = Step(
    id="step_04_leak",
    type="ask_choice",
    goal="Check for visible leaks around the tank.",
    background_context="Leaks reduce pressure and temperature. They are a major safety/damage risk.",
    warning="If you see a leak, turn off the water supply immediately to prevent damage.",
    options=[
        Option(
            id="leaking",
            label="Visible water leak detected around the hot water tank.",
            next_step_id="end_call_pro_leak"
        ),
        Option(
            id="dry",
            label="No visible leaks; the area around the tank is dry.",
            next_step_id="step_05_gas_smell"
        ),
    ]
)

# --- STEP 5: GAS SAFETY CHECK (From Section: "Broken Gas Valve") ---
step_05 = Step(
    id="step_05_gas_smell",
    type="ask_choice",
    goal="Safety check for gas leaks before suggesting internal repairs.",
    background_context="Rotten egg smell indicates a gas leak. This is an emergency.",
    warning="If you smell gas, leave the home and call 911/Gas Company.",
    options=[
        Option(
            id="gas_leak",
            label="Gas odor (rotten egg smell) detected near the water heater.",
            next_step_id="end_emergency_gas"
        ),
        Option(
            id="no_gas_issues",
            label="No gas smell present, or the unit is an electric water heater.",
            next_step_id="end_consult_pro_complex"
        ),
    ]
)

# ==============================================================================
# END STEPS (Outcomes)
# ==============================================================================

end_success_thermostat = Step(
    id="end_success_thermostat",
    type="end",
    goal="Close the session after a successful fix.",
)

end_monitor = Step(
    id="end_monitor",
    type="end",
    goal="Close the session but advise monitoring.",
)

end_wait_recovery = Step(
    id="end_wait_recovery",
    type="end",
    goal="Explain that the tank just needs to refill/reheat.",
)

end_call_pro_leak = Step(
    id="end_call_pro_leak",
    type="end",
    goal="Urgent referral for a leak.",
)

end_emergency_gas = Step(
    id="end_emergency_gas",
    type="end",
    goal="Emergency exit protocol.",
    warning="LEAVE THE HOME IMMEDIATELY.",
)

# --- CATCH-ALL FOR COMPLEX ISSUES (Sediment, Dip Tube, Elements) ---
# Since we are not branching to a "Drain Tank" workflow in this PR, 
# we group the complex causes (Section: Sediment, Dip Tube, Elements) here.
end_consult_pro_complex = Step(
    id="end_consult_pro_complex",
    type="end",
    goal="Refer user to a pro for complex internal diagnostics.",
    background_context=(
        "Remaining causes: Sediment build-up (requires draining), "
        "Broken Dip Tube, or Faulty Heating Elements. "
        "These require tools and disassembly."
    ),
)

# ==============================================================================
# WORKFLOW DEFINITION
# ==============================================================================

lukewarm_workflow = Workflow(
    name="troubleshoot_lukewarm_water",
    start_step="step_01_thermostat",
    steps={
        "step_01_thermostat": step_01,
        "step_02_breaker": step_02,
        "step_02a_reset_breaker": step_02a,
        "step_03_demand": step_03,
        "step_04_leak": step_04,
        "step_05_gas_smell": step_05,
        "end_success_thermostat": end_success_thermostat,
        "end_monitor": end_monitor,
        "end_wait_recovery": end_wait_recovery,
        "end_call_pro_leak": end_call_pro_leak,
        "end_emergency_gas": end_emergency_gas,
        "end_consult_pro_complex": end_consult_pro_complex
    }
)

HARDCODED_WORKFLOWS = {
    "troubleshoot_lukewarm_water": lukewarm_workflow
}