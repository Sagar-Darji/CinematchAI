"""LLM client wrapper for Ollama and Groq."""

import time
from enum import Enum
from typing import Any, Dict, List, Optional

import requests
from groq import Groq

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(str, Enum):
    """LLM provider options."""

    OLLAMA = "ollama"
    GROQ = "groq"


class LLMClient:
    """Unified LLM client supporting Ollama and Groq."""

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.OLLAMA,
        model: Optional[str] = None,
        fallback_provider: Optional[LLMProvider] = None,
    ):
        """
        Initialize LLM client.

        Args:
            provider: Primary LLM provider.
            model: Model name. If None, uses default from settings.
            fallback_provider: Fallback provider if primary fails.
        """
        self.settings = get_settings()
        self.provider = provider
        self.fallback_provider = fallback_provider

        # Set model
        if model:
            self.model = model
        else:
            self.model = (
                self.settings.ollama_model_main
                if provider == LLMProvider.OLLAMA
                else "llama-3.1-70b-versatile"
            )

        # Initialize Groq client if using Groq
        self.groq_client: Optional[Groq] = None
        if provider == LLMProvider.GROQ or fallback_provider == LLMProvider.GROQ:
            if self.settings.groq_api_key:
                self.groq_client = Groq(api_key=self.settings.groq_api_key)
            else:
                logger.warning("Groq API key not set. Groq provider unavailable.")

        logger.info(f"LLM Client initialized with provider: {provider}, model: {self.model}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
    ) -> str:
        """
        Generate completion from LLM.

        Args:
            prompt: User prompt.
            system_prompt: System prompt (optional).
            temperature: Sampling temperature (0-1).
            max_tokens: Maximum tokens to generate.
            stop: Stop sequences.

        Returns:
            Generated text.

        Raises:
            Exception: If all providers fail.
        """
        try:
            if self.provider == LLMProvider.OLLAMA:
                return self._generate_ollama(prompt, system_prompt, temperature, max_tokens, stop)
            elif self.provider == LLMProvider.GROQ:
                return self._generate_groq(prompt, system_prompt, temperature, max_tokens, stop)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except Exception as e:
            logger.error(f"Primary provider {self.provider} failed: {e}")

            # Try fallback provider
            if self.fallback_provider:
                logger.info(f"Attempting fallback provider: {self.fallback_provider}")
                try:
                    if self.fallback_provider == LLMProvider.OLLAMA:
                        return self._generate_ollama(
                            prompt, system_prompt, temperature, max_tokens, stop
                        )
                    elif self.fallback_provider == LLMProvider.GROQ:
                        return self._generate_groq(
                            prompt, system_prompt, temperature, max_tokens, stop
                        )
                except Exception as fallback_error:
                    logger.error(f"Fallback provider {self.fallback_provider} failed: {fallback_error}")

            raise Exception(f"All LLM providers failed. Last error: {e}")

    def _generate_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        stop: Optional[List[str]],
    ) -> str:
        """Generate completion from Ollama."""
        url = f"{self.settings.ollama_base_url}/api/generate"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if stop:
            payload["options"]["stop"] = stop

        logger.debug(f"Sending request to Ollama: {self.model}")
        start_time = time.time()

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        elapsed_time = time.time() - start_time
        logger.debug(f"Ollama request completed in {elapsed_time:.2f}s")

        result = response.json()
        return result.get("response", "")

    def _generate_groq(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        stop: Optional[List[str]],
    ) -> str:
        """Generate completion from Groq."""
        if not self.groq_client:
            raise Exception("Groq client not initialized. Check API key.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(f"Sending request to Groq: {self.model}")
        start_time = time.time()

        chat_completion = self.groq_client.chat.completions.create(
            messages=messages,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )

        elapsed_time = time.time() - start_time
        logger.debug(f"Groq request completed in {elapsed_time:.2f}s")

        return chat_completion.choices[0].message.content

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Chat-style interaction with LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            Generated text.
        """
        # Extract system prompt and user prompt
        system_prompt = None
        user_prompt = ""

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "user":
                user_prompt = msg["content"]

        return self.generate(user_prompt, system_prompt, temperature, max_tokens)


def get_llm_client(
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    use_fast_model: bool = False,
) -> LLMClient:
    """
    Get configured LLM client.

    Args:
        provider: LLM provider. If None, uses Ollama.
        model: Model name. If None, uses default.
        use_fast_model: Use fast model instead of main model.

    Returns:
        Configured LLM client.
    """
    settings = get_settings()
    provider = provider or LLMProvider.OLLAMA

    if not model:
        if use_fast_model:
            model = (
                settings.ollama_model_fast
                if provider == LLMProvider.OLLAMA
                else "llama-3.1-8b-instant"
            )
        else:
            model = (
                settings.ollama_model_main
                if provider == LLMProvider.OLLAMA
                else "llama-3.1-70b-versatile"
            )

    # Set fallback provider
    fallback_provider = LLMProvider.GROQ if provider == LLMProvider.OLLAMA else None

    return LLMClient(provider=provider, model=model, fallback_provider=fallback_provider)
