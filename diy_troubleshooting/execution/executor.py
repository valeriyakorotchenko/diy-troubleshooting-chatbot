"""
Executor - Agentic Step Execution Layer

This module defines the StepExecutor, a stateless class that wraps the LLM
for executing individual troubleshooting steps. The executor is responsible
for dynamic prompt construction and structured output parsing.
"""

import logging
from typing import List

from ..domain.models import Step
from ..state.models import Frame, Message
from .schemas.decisions import StepDecision
from ..llm.interface import LLMProvider
from .prompts import render, Template

logger = logging.getLogger(__name__)


class StepExecutor:
    # DEPENDENCY INJECTION: We ask for the generic Provider
    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    async def run_turn(
        self,
        step: Step,
        frame: Frame,
        user_input: str,
        history: List[Message]
    ) -> StepDecision:
        """
        Execute a turn within a step.

        Helps the user work toward the step's goal and generates an
        appropriate response. Determines if the goal has been achieved.
        """
        system_prompt = render(
            Template.STEP_EXECUTION,
            step=step,
            mailbox=frame.pending_child_result,
        )

        # Prepare Messages (System + History + New Input)
        # The role/content dict format is an industry standard across LLM providers.
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        if user_input:
            messages.append({"role": "user", "content": user_input})

        try:
            # Call LLM with Structured Output
            # CLEAN CALL: No dependency on OpenAI specifics here
            decision = await self._llm.generate_structured_output(
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