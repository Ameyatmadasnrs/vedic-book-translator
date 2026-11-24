"""Versioned prompt templates for literal, theological, literary, and terminology stages."""

from vedic_translator.translation_engine.prompts.system_prompt import (
    RAMCHARIT_MANAS_SYSTEM_PROMPT,
    build_ramcharit_manas_system_instruction,
)

__all__ = [
    "RAMCHARIT_MANAS_SYSTEM_PROMPT",
    "build_ramcharit_manas_system_instruction",
]
