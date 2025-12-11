from typing import List, Type, TypeVar
from openai import AsyncOpenAI
from pydantic import BaseModel

from ..interface import LLMProvider
from ...config import settings

T = TypeVar("T", bound=BaseModel)

class OpenAIAdapter(LLMProvider):
    def __init__(self, api_key: str, model_name: str = settings.OPENAI_MODEL):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model_name = model_name

    async def generate_structured_output(
        self, 
        messages: List[dict], 
        response_model: Type[T],
        temperature: float = 0.0
    ) -> T:
        # This is where the specific OpenAI implementation lives.
        # If OpenAI changes their API tomorrow, we ONLY change this file.
        completion = await self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=messages,
            response_format=response_model,
            temperature=temperature,
        )
        
        # We unwrap the specific OpenAI response structure here
        return completion.choices[0].message.parsed