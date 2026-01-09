from abc import ABC, abstractmethod
from typing import List, Type, TypeVar

from pydantic import BaseModel

# Generic type variable for the Pydantic model expected in structured responses.
T = TypeVar("T", bound=BaseModel)

class LLMProvider(ABC):
    """
    Abstract Base Class interface that defines the contract for any LLM provider 
    (OpenAI, Anthropic, Local LLaMA, etc.)
    """

    @abstractmethod
    async def generate_structured_output(
        self, 
        messages: List[dict], 
        response_model: Type[T],
        temperature: float = 0.0
    ) -> T:
        """
        Generates a response from the LLM strictly matching the Pydantic 'response_model'.
        """
        pass