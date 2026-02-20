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
                else "llama-3.3-70b-versatile"
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
        last_error: Optional[Exception] = None

        # Attempt primary provider (up to 3 retries for Groq rate-limit / transient errors)
        max_attempts = 3 if self.provider == LLMProvider.GROQ else 1
        for attempt in range(1, max_attempts + 1):
            try:
                if self.provider == LLMProvider.OLLAMA:
                    return self._generate_ollama(prompt, system_prompt, temperature, max_tokens, stop)
                elif self.provider == LLMProvider.GROQ:
                    return self._generate_groq(prompt, system_prompt, temperature, max_tokens, stop)
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")
            except Exception as e:
                last_error = e
                if attempt < max_attempts:
                    wait = attempt * 2  # 2s, 4s back-off
                    logger.warning(
                        f"Groq attempt {attempt}/{max_attempts} failed: {e} — retrying in {wait}s"
                    )
                    time.sleep(wait)
                else:
                    logger.error(f"Primary provider {self.provider} failed after {attempt} attempts: {e}")

        # Try fallback provider (once)
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
                raise Exception(f"All LLM providers failed. Last error: {fallback_error}")

        raise Exception(f"All LLM providers failed. Last error: {last_error}")

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
    """Get configured LLM client.

    Provider priority (when provider=None):
    1. If settings.llm_provider == 'groq' AND groq_api_key is set → Groq primary, Ollama fallback
    2. If settings.llm_provider == 'groq' but no API key → Ollama (warn)
    3. If settings.llm_provider == 'ollama' → Ollama primary, no fallback

    Args:
        provider: Override provider. If None, auto-selects based on settings.
        model: Override model name. If None, uses default for the chosen provider.
        use_fast_model: Use fast/cheap model instead of the main model.

    Returns:
        Configured LLM client.
    """
    settings = get_settings()

    # Auto-select provider from settings if not overridden
    if provider is None:
        if settings.llm_provider == "groq" and settings.groq_api_key:
            provider = LLMProvider.GROQ
        else:
            if settings.llm_provider == "groq" and not settings.groq_api_key:
                logger.warning(
                    "LLM_PROVIDER=groq but GROQ_API_KEY is not set — falling back to Ollama"
                )
            provider = LLMProvider.OLLAMA

    # Pick model for the chosen provider
    if not model:
        if provider == LLMProvider.GROQ:
            model = settings.groq_model_fast if use_fast_model else settings.groq_model_main
        else:
            model = settings.ollama_model_fast if use_fast_model else settings.ollama_model_main

    # Groq gets Ollama as fallback; Ollama has no fallback
    fallback_provider = LLMProvider.OLLAMA if provider == LLMProvider.GROQ else None

    logger.info(
        f"LLM: {provider.value} ({model})"
        + (f" → fallback: {fallback_provider.value}" if fallback_provider else "")
    )
    return LLMClient(provider=provider, model=model, fallback_provider=fallback_provider)
