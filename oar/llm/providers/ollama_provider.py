"""Ollama provider — use local Ollama server as an LLM backend."""

from __future__ import annotations

from typing import Any

from oar.llm.providers.base import LLMResponse, LLMProviderError


class OllamaProvider:
    """Use local Ollama server as an LLM backend.

    Requires Ollama to be running on localhost:11434.
    No API key needed — fully offline capable.
    """

    DEFAULT_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3.1"

    def __init__(self, base_url: str = DEFAULT_URL, timeout: int = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def available(self) -> bool:
        """True when Ollama server is reachable."""
        return self.health_check()

    def health_check(self) -> bool:
        """Check if Ollama server is responding."""
        try:
            import httpx

            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List available Ollama models."""
        try:
            import httpx

            response = httpx.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            return []

    def complete(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send completion request to Ollama chat API."""
        import httpx

        effective_model = model or self.DEFAULT_MODEL
        # Strip any "ollama/" prefix from model name.
        if effective_model.startswith("ollama/"):
            effective_model = effective_model[7:]

        # Convert messages to Ollama format.
        ollama_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                ollama_messages.append({"role": "system", "content": content})
            elif role == "assistant":
                ollama_messages.append({"role": "assistant", "content": content})
            else:
                ollama_messages.append({"role": "user", "content": content})

        payload = {
            "model": effective_model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError as exc:
            raise LLMProviderError(
                self.name,
                f"Cannot connect to Ollama at {self.base_url}",
                recoverable=True,
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                self.name,
                f"Ollama request timed out ({self.timeout}s)",
                recoverable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                self.name,
                f"Ollama returned {exc.response.status_code}: {exc.response.text[:200]}",
                recoverable=True,
            ) from exc

        content = data.get("message", {}).get("content", "")
        # Ollama doesn't always report token counts accurately,
        # but eval_count and prompt_eval_count are usually available.
        output_tokens = data.get("eval_count", 0)
        input_tokens = data.get("prompt_eval_count", 0)

        return LLMResponse(
            content=content,
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=0.0,  # Local inference is free
        )

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate."""
        return len(text) // 4
