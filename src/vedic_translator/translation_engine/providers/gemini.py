"""Gemini AI translation provider using the official google-genai SDK Interactions API."""

import json
import os
import re
import time
from typing import Any

from loguru import logger

from vedic_translator.core.exceptions import (
    AuthenticationError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitExceededError,
)
from vedic_translator.translation_engine.prompts import (
    RAMCHARIT_MANAS_SYSTEM_PROMPT,
)
from vedic_translator.translation_engine.providers.base import (
    ConfidenceAssessment,
    ITranslationProvider,
    ProviderConfig,
    ProviderHealthCheck,
    TokenUsage,
    TranslationPayload,
    TranslationResponse,
)

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

# Default system instruction for Ramcharit Manas translation into Russian
DEFAULT_SYSTEM_INSTRUCTION = RAMCHARIT_MANAS_SYSTEM_PROMPT


class GeminiTranslationProvider(ITranslationProvider):
    """Concrete translation provider leveraging Google Gemini via the Interactions API."""

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = DEFAULT_GEMINI_MODEL,
        client: Any = None,
    ) -> None:
        """Initialize the Gemini translation provider.

        Args:
            api_key: Explicit API key. If omitted, read from GEMINI_API_KEY environment variable.
            default_model: Configurable model ID (defaults to gemini-3.5-flash-lite).
            client: Optional pre-configured or mocked client for dependency injection.
        """
        self._default_model = default_model
        resolved_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self._api_key = resolved_key

        if client is not None:
            self._client = client
        else:
            if not resolved_key:
                raise AuthenticationError(
                    "GEMINI_API_KEY is not configured. Provide an explicit key or set GEMINI_API_KEY."
                )
            # Late import so google-genai dependency remains isolated to this provider
            from google import genai

            self._client = genai.Client(api_key=resolved_key)

    @property
    def provider_name(self) -> str:
        """Return canonical provider identifier."""
        return "gemini"

    @property
    def default_model(self) -> str:
        """Return configured default model ID."""
        return self._default_model

    def translate(
        self,
        payload: TranslationPayload,
        config: ProviderConfig | None = None,
    ) -> TranslationResponse:
        """Translate a single unit payload into Russian using the Interactions API.

        Args:
            payload: Input translation unit with original text, phonetics, and context.
            config: Optional per-request configuration overrides (model, temperature, etc.).

        Returns:
            Normalized TranslationResponse with Russian text, notes, and token metrics.

        Raises:
            AuthenticationError: On invalid credentials or permission failure.
            RateLimitExceededError: On HTTP 429 / quota exhaustion.
            ProviderTimeoutError: On request timeout.
            ProviderError: On malformed, empty, or unparseable responses.
        """
        active_model = (config and config.model) or self._default_model
        system_instruction = payload.system_instruction or DEFAULT_SYSTEM_INSTRUCTION
        user_prompt = self._format_user_prompt(payload)

        create_kwargs: dict[str, Any] = {
            "model": active_model,
            "input": user_prompt,
            "system_instruction": system_instruction,
        }

        # Forward supported configuration options genuinely supported by Interactions API
        if config is not None:
            if config.timeout_seconds is not None:
                create_kwargs["timeout"] = config.timeout_seconds

            gen_config: dict[str, Any] = {}
            if config.temperature is not None:
                gen_config["temperature"] = config.temperature
            if config.max_output_tokens is not None:
                gen_config["max_output_tokens"] = config.max_output_tokens

            if gen_config:
                create_kwargs["generation_config"] = gen_config

        try:
            logger.debug(
                f"Calling Gemini ({active_model}) for unit {payload.canonical_id or payload.unit_id}"
            )
            interaction = self._client.interactions.create(**create_kwargs)
        except Exception as e:
            mapped_exc = self._map_exception(e)
            logger.error(f"Gemini API request failed for unit {payload.canonical_id}: {mapped_exc}")
            raise mapped_exc from e

        raw_text = self._extract_text_from_interaction(interaction)
        token_usage = self._extract_token_usage(interaction)

        return self._parse_response_json(
            raw_text=raw_text,
            expected_canonical_id=payload.canonical_id,
            model_name=active_model,
            token_usage=token_usage,
        )

    def validate_connection(self) -> ProviderHealthCheck:
        """Perform a lightweight health check to verify API key validity and reachability.

        Returns:
            ProviderHealthCheck with status OK or ERROR and measured latency.
        """
        start_time = time.perf_counter()
        test_prompt = "Reply with exactly: GEMINI_API_CONNECTION_OK"

        try:
            interaction = self._client.interactions.create(
                model=self._default_model,
                input=test_prompt,
            )
            raw_text = self._extract_text_from_interaction(interaction)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return ProviderHealthCheck(
                provider_name=self.provider_name,
                model_name=self._default_model,
                status="OK",
                latency_ms=latency_ms,
                details={"response_text": raw_text.strip()},
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            sanitized_err = self._sanitize_secret(str(e))
            return ProviderHealthCheck(
                provider_name=self.provider_name,
                model_name=self._default_model,
                status="ERROR",
                latency_ms=latency_ms,
                details={"error": sanitized_err, "error_type": type(e).__name__},
            )

    def _format_user_prompt(self, payload: TranslationPayload) -> str:
        """Format the structured TranslationPayload into a tagged input string."""
        parts: list[str] = [
            f"<CANONICAL_ID>{payload.canonical_id or 'UNKNOWN'}</CANONICAL_ID>",
            f"<UNIT_TYPE>{payload.unit_type}</UNIT_TYPE>",
        ]
        if payload.canto_name:
            parts.append(f"<CANTO>{payload.canto_name}</CANTO>")
        if payload.narrative_episode:
            parts.append(f"<EPISODE>{payload.narrative_episode}</EPISODE>")
        if payload.active_speakers:
            parts.append(f"<SPEAKERS>{payload.active_speakers}</SPEAKERS>")

        parts.append(f"<ORIGINAL_SOURCE>\n{payload.original_text.strip()}\n</ORIGINAL_SOURCE>")

        if payload.transliteration:
            parts.append(
                f"<IAST_TRANSLITERATION>\n{payload.transliteration.strip()}\n</IAST_TRANSLITERATION>"
            )

        if payload.reference_translation:
            parts.append(
                f"<ENGLISH_REFERENCE>\n{payload.reference_translation.strip()}\n</ENGLISH_REFERENCE>"
            )

        if payload.commentary:
            parts.append(f"<COMMENTARY>\n{payload.commentary.strip()}\n</COMMENTARY>")

        if payload.glossary_terms:
            glossary_lines: list[str] = []
            for g in payload.glossary_terms:
                decl_str = (
                    ", ".join(f"{k}: {v}" for k, v in g.declensions.items())
                    if g.declensions
                    else "none"
                )
                notes_str = f" ({g.notes})" if g.notes else ""
                glossary_lines.append(
                    f"- {g.term} -> {g.canonical_russian} [declensions: {decl_str}]{notes_str}"
                )
            parts.append("<GLOSSARY>\n" + "\n".join(glossary_lines) + "\n</GLOSSARY>")

        if payload.preceding_context:
            context_lines: list[str] = []
            for ctx in payload.preceding_context:
                cid = f"[{ctx.canonical_id}] " if ctx.canonical_id else ""
                context_lines.append(f"{cid}{ctx.russian_verse}")
            parts.append(
                "<PRECEDING_CONTEXT>\n" + "\n".join(context_lines) + "\n</PRECEDING_CONTEXT>"
            )

        if payload.custom_instructions:
            parts.append(
                f"<ADDITIONAL_INSTRUCTIONS>\n{payload.custom_instructions.strip()}\n</ADDITIONAL_INSTRUCTIONS>"
            )

        return "\n\n".join(parts)

    def _extract_text_from_interaction(self, interaction: Any) -> str:
        """Extract output text from an interaction result across unary and stepped models."""
        text = getattr(interaction, "output_text", None)
        if text:
            return str(text).strip()

        if hasattr(interaction, "steps"):
            parts: list[str] = []
            for step in getattr(interaction, "steps", []):
                if getattr(step, "type", "") == "model_output":
                    for item in getattr(step, "content", []):
                        if getattr(item, "type", "") == "text":
                            t = getattr(item, "text", "")
                            if t:
                                parts.append(t)
            if parts:
                return "".join(parts).strip()

        return ""

    def _extract_token_usage(self, interaction: Any) -> TokenUsage | None:
        """Extract standardized TokenUsage metrics from an interaction result."""
        usage = getattr(interaction, "usage", None)
        if not usage:
            return None

        input_toks = (
            getattr(usage, "total_input_tokens", None)
            or getattr(usage, "initial_input_tokens", 0)
            or 0
        )
        output_toks = getattr(usage, "total_output_tokens", 0) or 0
        total_toks = getattr(usage, "total_tokens", 0) or (input_toks + output_toks)
        cached_toks = getattr(usage, "total_cached_tokens", 0) or 0

        return TokenUsage(
            input_tokens=input_toks,
            output_tokens=output_toks,
            total_tokens=total_toks,
            cached_tokens=cached_toks,
        )

    def _parse_response_json(
        self,
        raw_text: str,
        expected_canonical_id: str | None,
        model_name: str,
        token_usage: TokenUsage | None,
    ) -> TranslationResponse:
        """Parse raw model output into a validated TranslationResponse."""
        if not raw_text.strip():
            raise ProviderError("Empty response received from Gemini provider.")

        cleaned = raw_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ProviderError(
                f"Failed to parse JSON response from Gemini: {e}",
                details={"raw_response": raw_text[:300]},
            ) from e

        if not isinstance(data, dict):
            raise ProviderError(
                "Gemini response JSON root must be an object.",
                details={"raw_response": raw_text[:300]},
            )

        russian_verse = data.get("russian_verse")
        if not russian_verse or not str(russian_verse).strip():
            raise ProviderError(
                "Gemini response JSON is missing required 'russian_verse' field.",
                details={"parsed_keys": list(data.keys())},
            )

        conf_data = data.get("confidence_assessment")
        confidence = ConfidenceAssessment()
        if isinstance(conf_data, dict):
            confidence = ConfidenceAssessment(
                linguistic_certainty=str(conf_data.get("linguistic_certainty", "HIGH")),
                theological_clarity=str(conf_data.get("theological_clarity", "HIGH")),
                ambiguity_notes=conf_data.get("ambiguity_notes"),
            )

        return TranslationResponse(
            canonical_id=data.get("canonical_id") or expected_canonical_id,
            russian_verse=str(russian_verse).strip(),
            russian_commentary=data.get("russian_commentary"),
            translator_notes=data.get("translator_notes"),
            confidence_assessment=confidence,
            model_name=model_name,
            token_usage=token_usage,
            raw_response=raw_text,
        )

    def _sanitize_secret(self, text: str) -> str:
        """Ensure API key never appears in any error message or log."""
        if self._api_key and self._api_key in text:
            return text.replace(self._api_key, "[REDACTED_API_KEY]")
        return text

    def _map_exception(self, exc: Exception) -> Exception:
        """Map SDK errors to strongly typed domain exceptions while redacting secrets."""
        err_msg = self._sanitize_secret(str(exc))
        err_lower = err_msg.lower()
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

        if (
            status_code in (401, 403)
            or "api key not valid" in err_lower
            or "unauthenticated" in err_lower
            or "permission_denied" in err_lower
        ):
            return AuthenticationError(
                f"Gemini authentication failed: {err_msg}",
                details={"status_code": status_code},
            )

        if (
            status_code == 429
            or "resource_exhausted" in err_lower
            or "quota" in err_lower
            or "rate limit" in err_lower
        ):
            return RateLimitExceededError(
                f"Gemini rate limit exceeded: {err_msg}",
                details={"status_code": status_code},
            )

        if "timeout" in err_lower or "timed out" in err_lower:
            return ProviderTimeoutError(
                f"Gemini request timed out: {err_msg}",
                details={"status_code": status_code},
            )

        details: dict[str, Any] = {
            "status_code": status_code,
            "error_type": type(exc).__name__,
        }

        # Detect transient service availability and capacity bottlenecks (e.g. HTTP 503)
        is_503 = status_code in (503, "503")
        is_unavailable = "service_unavailable" in err_lower or "high demand" in err_lower
        if is_503 or is_unavailable:
            details["is_transient"] = True

        return ProviderError(
            f"Gemini API error: {err_msg}",
            details=details,
        )
