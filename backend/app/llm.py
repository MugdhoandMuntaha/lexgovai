"""LLM + embedding access. `GeminiClient` is the production implementation; tests inject a fake."""

from __future__ import annotations

import logging
import time
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

EmbeddingTask = str  # "RETRIEVAL_DOCUMENT" | "RETRIEVAL_QUERY"


class LLMNotConfiguredError(RuntimeError):
    """Raised when an endpoint needs the LLM but no API key is configured."""


class LLMError(RuntimeError):
    """Raised when the LLM call fails or returns output that does not match the schema."""


class LLMClient(Protocol):
    model_name: str

    def generate_json(self, prompt: str, schema: type[T], system: str) -> T: ...

    def embed(self, texts: list[str], task: EmbeddingTask) -> list[list[float]]: ...

    def generate_text_with_image(
        self, prompt: str, image_bytes: bytes, mime_type: str = "image/png", system: str = ""
    ) -> str: ...


class GeminiClient:
    """Thin wrapper around the google-genai SDK with structured output and simple retries."""

    _EMBED_BATCH = 100
    _ATTEMPTS = 3

    def __init__(self, api_key: str, model: str, embedding_model: str, embedding_dimensions: int):
        # Imported lazily so the rest of the app (and the tests) never touch the SDK.
        from google import genai
        from google.genai import types

        self._genai_types = types
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=15000))
        self.model_name = model
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions

    def _retry(self, fn, what: str):
        last_exc: Exception | None = None
        for attempt in range(1, self._ATTEMPTS + 1):
            try:
                return fn()
            except Exception as exc:  # SDK raises a variety of transport/API errors
                last_exc = exc
                logger.warning("Gemini %s failed (attempt %d/%d): %s", what, attempt, self._ATTEMPTS, exc)
                if attempt < self._ATTEMPTS:
                    time.sleep(1.5 * attempt)
        raise LLMError(f"Gemini {what} failed: {last_exc}") from last_exc

    FALLBACK_MODELS = ("gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite")

    def generate_json(self, prompt: str, schema: type[T], system: str) -> T:
        types = self._genai_types
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
        )

        candidate_models = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]
        last_exc: Exception | None = None

        for model in candidate_models:
            for attempt in range(1, 3):
                try:
                    response = self._client.models.generate_content(model=model, contents=prompt, config=config)
                    if isinstance(response.parsed, schema):
                        return response.parsed
                    if not response.text:
                        raise LLMError("Gemini returned an empty response")
                    try:
                        return schema.model_validate_json(response.text)
                    except ValidationError as exc:
                        raise LLMError(f"Gemini response did not match {schema.__name__}: {exc}") from exc
                except Exception as exc:
                    last_exc = exc
                    logger.warning("Gemini generation (%s) with model %s failed (attempt %d/2): %s", schema.__name__, model, attempt, exc)
                    err_msg = str(exc).lower()
                    if "404" in err_msg or "not_found" in err_msg or "no longer available" in err_msg:
                        break  # Immediately advance to next fallback model
                    time.sleep(1.0 * attempt)

        raise LLMError(f"Gemini generation ({schema.__name__}) failed across all fallback models: {last_exc}") from last_exc

    def generate_text_with_image(
        self, prompt: str, image_bytes: bytes, mime_type: str = "image/png", system: str = ""
    ) -> str:
        types = self._genai_types
        config = types.GenerateContentConfig(
            system_instruction=system if system else None,
        )
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        candidate_models = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]
        last_exc: Exception | None = None

        for model in candidate_models:
            for attempt in range(1, 3):
                try:
                    response = self._client.models.generate_content(
                        model=model,
                        contents=[part, prompt],
                        config=config,
                    )
                    return (response.text or "").strip()
                except Exception as exc:
                    last_exc = exc
                    logger.warning("Gemini vision OCR with model %s failed (attempt %d/2): %s", model, attempt, exc)
                    err_msg = str(exc).lower()
                    if "404" in err_msg or "not_found" in err_msg or "no longer available" in err_msg:
                        break
                    time.sleep(1.0 * attempt)

        raise LLMError(f"Gemini vision OCR text generation failed across all fallback models: {last_exc}") from last_exc

    def embed(self, texts: list[str], task: EmbeddingTask) -> list[list[float]]:
        types = self._genai_types
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._EMBED_BATCH):
            batch = texts[start : start + self._EMBED_BATCH]
            config = types.EmbedContentConfig(task_type=task, output_dimensionality=self._embedding_dimensions)

            def call(batch=batch, config=config):
                return self._client.models.embed_content(model=self._embedding_model, contents=batch, config=config)

            result = self._retry(call, "embedding")
            vectors.extend(list(e.values) for e in result.embeddings)
        return vectors
