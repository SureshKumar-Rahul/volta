"""Universal LLM client: the OpenAI SDK pointed at any OpenAI-compatible
provider, selected by environment variable. Keys are read from the environment
only, never from disk."""

import os

from openai import OpenAI

PROVIDERS = {
    "groq": {"base_url": "https://api.groq.com/openai/v1",
             "model": "llama-3.3-70b-versatile", "key_env": "GROQ_API_KEY"},
    "openai": {"base_url": "https://api.openai.com/v1",
               "model": "gpt-4o-mini", "key_env": "OPENAI_API_KEY"},
    "scads": {"base_url": "https://llm.scads.ai/v1",
              "model": "meta-llama/Llama-3.3-70B-Instruct", "key_env": "SCADS_API_KEY"},
    "ollama": {"base_url": "http://localhost:11434/v1",
               "model": "llama3.1", "key_env": None},
}
DEFAULT_PROVIDER = "groq"


def resolve_config():
    env = os.environ.get("LLM_PROVIDER")
    if env:
        provider = env.lower()
    elif os.environ.get("LLM_BASE_URL"):
        provider = "custom"
    else:
        provider = DEFAULT_PROVIDER
    preset = PROVIDERS.get(provider, {})
    base_url = os.environ.get("LLM_BASE_URL") or preset.get("base_url")
    model = os.environ.get("LLM_MODEL") or preset.get("model")
    key = os.environ.get("LLM_API_KEY")
    if not key and preset.get("key_env"):
        key = os.environ.get(preset["key_env"])
    if not key and provider == "ollama":
        key = "ollama"
    return provider, base_url, model, key


def get_client_and_model():
    provider, base_url, model, key = resolve_config()
    if not base_url:
        raise SystemExit(f"No base URL for provider '{provider}'. Set LLM_BASE_URL "
                         f"or LLM_PROVIDER (one of: {', '.join(PROVIDERS)}).")
    if not model:
        raise SystemExit(f"No model for provider '{provider}'. Set LLM_MODEL.")
    if not key:
        hint = (PROVIDERS.get(provider) or {}).get("key_env") or "LLM_API_KEY"
        raise SystemExit(f"No API key for provider '{provider}'. Set {hint} (or "
                         f"LLM_API_KEY) as a process-scoped environment variable.")
    return OpenAI(base_url=base_url, api_key=key), model
