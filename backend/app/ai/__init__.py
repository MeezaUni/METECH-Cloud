"""AI engine selection. The cloud edition ships with Google Gemini."""
from .base import AIContext, AIProvider, AIUnavailable
from .gemini import build_provider

__all__ = ["AIContext", "AIProvider", "AIUnavailable", "build_provider"]
