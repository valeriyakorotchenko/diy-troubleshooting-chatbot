from diy_troubleshooting.domain.models import Option, Step, StepType, Workflow, WorkflowLink

# ==============================================================================
# STEP DEFINITIONS
# ==============================================================================

# --- STEP 1: THERMOSTAT (From Section: "Check and Adjust the Thermostat") ---
step_01 = Step(
    id="step_01_thermostat",
    type=StepType.ASK_CHOICE,
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
    type=StepType.ASK_CHOICE,
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
    type=StepType.INSTRUCTION,
    goal="Guide user to reset the breaker and test.",
    background_context="Flip to OFF, then firmly back to ON. Wait an hour or so to see if the water heats up. If it trips again immediately, you have an electrical short.",
    next_step="end_monitor"
)

# --- STEP 3: HIGH DEMAND (From Section: "Unmanageable Hot Water Demand") ---
step_03 = Step(
    id="step_03_demand",
    type=StepType.ASK_CHOICE,
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
            next_step_id="step_04_sediment"
        ),
    ]
)

# --- STEP 4: SEDIMENT BUILD-UP (From Section: "Sediment Build-Up") ---
step_04 = Step(
    id="step_04_sediment",
    type=StepType.ASK_CHOICE,
    goal="Determine if sediment build-up is blocking the heat transfer.",
    background_context=(
        "Over time, minerals in the water "
        "sink to the bottom of the tank and stick to the heating elements, reducing the amount of "
        "heat transferred from the heating elements to the water, causing lukewarm water."
    ),
    suggested_links=[
        WorkflowLink(
            target_workflow_id="drain_water_heater",
            title="How to Drain a Water Heater",
            rationale=(
                "To check for sediment buildup, the user may need to drain and flush the water heater first. "
                "This sub-workflow guides them through the draining process safely."
            ),
            trigger_keywords=["drain", "flush", "how to drain", "empty tank", "sediment removal"]
        )
    ],
    options=[
        Option(
            id="sediment_buildup_detected",
            label="User confirms that there is sediment build-up inside the water heater.",
            next_step_id="end_sediment_resolved"
        ),
        Option(
            id="no_sediment_issue",
            label="User does not have hard water issues, tank was recently flushed, or sediment was not there after flushing the tank.",
            next_step_id="step_05_leak"
        ),
    ]
)


# --- STEP 5: LEAK CHECK (From Section: "Leaking Hot Water Tank") ---
step_05 = Step(
    id="step_05_leak",
    type=StepType.ASK_CHOICE,
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
            next_step_id="step_06_gas_smell"
        ),
    ]
)

# --- STEP 6: GAS SAFETY CHECK (From Section: "Broken Gas Valve") ---
step_06 = Step(
    id="step_06_gas_smell",
    type=StepType.ASK_CHOICE,
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
    type=StepType.END,
    goal="Close the session after a successful fix.",
)

end_monitor = Step(
    id="end_monitor",
    type=StepType.END,
    goal="Close the session but advise monitoring.",
)

end_wait_recovery = Step(
    id="end_wait_recovery",
    type=StepType.END,
    goal="Explain that the tank just needs to refill/reheat.",
)

end_sediment_resolved = Step(
    id="end_sediment_resolved",
    type=StepType.END,
    goal="Close the session after advising on sediment removal via tank flush.",
)

end_call_pro_leak = Step(
    id="end_call_pro_leak",
    type=StepType.END,
    goal="Urgent referral for a leak.",
)

end_emergency_gas = Step(
    id="end_emergency_gas",
    type=StepType.END,
    goal="Emergency exit protocol.",
    warning="LEAVE THE HOME IMMEDIATELY.",
)

# --- CATCH-ALL FOR COMPLEX ISSUES (Dip Tube, Elements) ---
# Sediment has its own diagnostic branch now. Remaining complex causes are grouped here.
end_consult_pro_complex = Step(
    id="end_consult_pro_complex",
    type=StepType.END,
    goal="Refer user to a pro for complex internal diagnostics.",
    background_context=(
        "Remaining causes: Broken Dip Tube or Faulty Heating Elements. "
        "These require specialized tools and disassembly."
    ),
)

# ==============================================================================
# DRAIN WATER HEATER WORKFLOW (Sub-workflow)
# ==============================================================================

# --- DRAIN STEP 1: TURN OFF POWER/GAS ---
drain_step_01 = Step(
    id="drain_step_01_power_off",
    type=StepType.INSTRUCTION,
    goal="Guide user to turn off power or gas to the water heater.",
    background_context=(
        "For electric heaters: flip the circuit breaker to OFF. "
        "For gas heaters: turn the gas valve to OFF or set thermostat to 'Pilot'. "
        "This prevents damage to heating elements and ensures safety."
    ),
    warning="Never drain with power on - heating elements will burn out if exposed to air.",
    next_step="drain_step_02_water_off"
)

# --- DRAIN STEP 2: TURN OFF WATER SUPPLY ---
drain_step_02 = Step(
    id="drain_step_02_water_off",
    type=StepType.INSTRUCTION,
    goal="Guide user to shut off the cold water supply.",
    background_context=(
        "Find the cold water inlet valve at the top of the heater. Turn it clockwise to close. "
        "If there's no dedicated valve, shut off the main water supply."
    ),
    next_step="drain_step_03_attach_hose"
)

# --- DRAIN STEP 3: ATTACH HOSE AND DRAIN ---
drain_step_03 = Step(
    id="drain_step_03_attach_hose",
    type=StepType.INSTRUCTION,
    goal="Guide user to connect a hose and drain the tank.",
    background_context=(
        "Connect a garden hose to the drain valve near the bottom of the tank. "
        "Run the hose to a drain or outside. Open a hot water faucet in the house to allow air in. "
        "Open the drain valve and let the tank empty (20-60 minutes for a full tank)."
    ),
    warning="The water will be HOT. Keep the hose secure and away from children and pets.",
    next_step="drain_end_success"
)


# --- DRAIN END: SUCCESS ---
drain_end_success = Step(
    id="drain_end_success",
    type=StepType.END,
    goal="Confirm successful completion of the drain procedure.",
    background_context=(
        "The tank has been drained."
    ),
)

# ==============================================================================
# WORKFLOW DEFINITIONS
# ==============================================================================

drain_water_heater_workflow = Workflow(
    name="drain_water_heater",
    title="How to Drain a Water Heater",
    start_step="drain_step_01_power_off",
    steps={
        "drain_step_01_power_off": drain_step_01,
        "drain_step_02_water_off": drain_step_02,
        "drain_step_03_attach_hose": drain_step_03,
        "drain_end_success": drain_end_success,
    }
)

lukewarm_workflow = Workflow(
    name="troubleshoot_lukewarm_water",
    title="Fix Lukewarm Water",
    start_step="step_01_thermostat",
    steps={
        "step_01_thermostat": step_01,
        "step_02_breaker": step_02,
        "step_02a_reset_breaker": step_02a,
        "step_03_demand": step_03,
        "step_04_sediment": step_04,
        "step_05_leak": step_05,
        "step_06_gas_smell": step_06,
        "end_success_thermostat": end_success_thermostat,
        "end_monitor": end_monitor,
        "end_wait_recovery": end_wait_recovery,
        "end_sediment_resolved": end_sediment_resolved,
        "end_call_pro_leak": end_call_pro_leak,
        "end_emergency_gas": end_emergency_gas,
        "end_consult_pro_complex": end_consult_pro_complex
    }
)

HARDCODED_WORKFLOWS = {
    "troubleshoot_lukewarm_water": lukewarm_workflow,
    "drain_water_heater": drain_water_heater_workflow
}