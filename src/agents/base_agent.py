"""Base agent class for CineMatch AI agents."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.utils.llm_client import LLMClient, LLMProvider, get_llm_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(
        self,
        name: str,
        description: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        use_fast_model: bool = False,
    ):
        """
        Initialize base agent.

        Args:
            name: Agent name.
            description: Agent description.
            model: LLM model to use. If None, uses default.
            temperature: Sampling temperature.
            use_fast_model: Use fast model (8B) instead of main (70B).
        """
        self.name = name
        self.description = description
        self.temperature = temperature

        # Initialize LLM client
        self.llm_client = get_llm_client(
            model=model,
            use_fast_model=use_fast_model,
        )

        logger.info(f"Initialized agent: {self.name}")

    @abstractmethod
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process state and return updated state.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with agent's contributions.
        """
        pass

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate LLM response.

        Args:
            prompt: User prompt.
            system_prompt: System prompt.
            max_tokens: Maximum tokens.

        Returns:
            Generated text.
        """
        return self.llm_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

    def log_processing(self, step: str) -> None:
        """
        Log processing step.

        Args:
            step: Description of processing step.
        """
        logger.info(f"[{self.name}] {step}")

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(name='{self.name}')"
