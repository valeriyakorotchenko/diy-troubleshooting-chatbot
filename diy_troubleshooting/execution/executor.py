"""
Executor - Agentic Step Execution Layer

This module defines the StepExecutor, a stateless class that wraps the LLM
for executing individual troubleshooting steps. The executor is responsible
for dynamic prompt construction and structured output parsing.
"""

import logging
from typing import List
from ..domain.models import Step, StepType
from ..state.models import Frame, Message
from ..schemas.decisions import StepDecision
from ..llm.interface import LLMProvider

logger = logging.getLogger(__name__)

class StepExecutor:
    # 1. DEPENDENCY INJECTION: We ask for the generic Provider
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    async def run_turn(
        self, 
        step: Step, 
        frame: Frame, 
        user_input: str, 
        history: List[Message]
    ) -> StepDecision:
        
        # 1. Build the Dynamic System Prompt
        system_prompt = self._build_system_prompt(step, frame)

        # 2. Prepare Messages (System + History + New Input)
        # Convert our Message objects to OpenAI format.
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        if user_input:
            messages.append({"role": "user", "content": user_input})

        try:
            # 3. Call LLM with Structured Output
            # CLEAN CALL: No dependency on OpenAI specifics here
            decision = await self.llm.generate_structured_output(
                messages=messages,
                response_model=StepDecision
            )
            return decision

        except Exception as e:
            logger.error(f"LLM Execution failed: {e}")
            return StepDecision(
                reply_to_user="System Error. Please try again.",
                status="IN_PROGRESS",
                reasoning=f"Error: {str(e)}"
            )


    def _build_system_prompt(self, step: Step, frame: Frame) -> str:
        """
        Constructs the prompt by injecting context from the current Step and Frame.
        """
        
        # --- CORE ---
        prompt = (
            "You are an expert DIY Home Repair Assistant. "
            "You are guiding a user through a specific troubleshooting step.\n\n"
        )

        # --- GOAL INJECTION ---
        prompt += f"CURRENT STEP GOAL: {step.goal}\n"
        prompt += f"CONTEXT: {step.background_context}\n\n"

        # --- WARNING INJECTION ---
        if step.warning:
            prompt += f"CRITICAL SAFETY WARNING: {step.warning}\n"
            prompt += "You MUST ensure the user acknowledges this warning before proceeding.\n\n"

        # --- CHILD WORKFLOW RETURN (The 'Mailbox' Check) ---
        if frame.pending_child_result:
            result = frame.pending_child_result
            prompt += "SYSTEM NOTIFICATION: A sub-task has just finished.\n"
            prompt += f"Sub-task Status: {result.status}\n"
            prompt += f"Sub-task Summary: {result.summary}\n"
            prompt += "INSTRUCTION: Welcome the user back. Use this result to determine if the current step goal is now met.\n\n"

        # --- LOGIC & OUTPUT INSTRUCTIONS ---
        prompt += "INSTRUCTIONS:\n"
        prompt += "1. If the user has satisfied the Goal (or confirmed the action), set status='COMPLETE'.\n"
        prompt += "2. If the user is struggling or asks for help, provide guidance based on the Context.\n"
        prompt += "3. If the user encounters a danger or cannot perform the step, set status='GIVE_UP'.\n"

        # --- OPTION HANDLING (Troubleshooting Flow Decision Trees) ---
        if step.type == "ask_choice" and step.options:
            prompt += "\nVALID OUTCOMES (for 'result_value' when COMPLETE):\n"
            for opt in step.options:
                prompt += f"- ID: '{opt.id}' | Description: {opt.label}\n"
            prompt += "When status is COMPLETE, you MUST set 'result_value' to one of the IDs above.\n"

        # --- HELPER WORKFLOW LINKS (Branching to Sub-Workflows) ---
        if step.suggested_links:
            prompt += "\nAVAILABLE HELPER WORKFLOWS:\n"
            prompt += "If the user explicitly asks for help with a related sub-task, you can branch to one of these workflows.\n"
            for link in step.suggested_links:
                prompt += f"- ID: '{link.target_workflow_id}' | Title: {link.title}\n"
                prompt += f"  When to offer: {link.rationale}\n"
            prompt += "\nTo branch to a helper workflow:\n"
            prompt += "- Set status='CALL_WORKFLOW'\n"
            prompt += "- Set result_value to the workflow ID\n"
            prompt += "IMPORTANT: Only use CALL_WORKFLOW when the user clearly needs or requests the sub-task. "
            prompt += "Do not proactively suggest branching unless the user is stuck.\n"

        logger.debug(f"Built system prompt for step {step.id}")

        return prompt