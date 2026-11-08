---
name: model-string-hygiene
description: "This skill should be used when adding or changing an LLM provider, model name or API call, or when a model returns 404, \"model not found\", deprecated or retired errors."
triggers:
- model name
- gemini
- groq
- llm provider
- deprecated model
- model not found
---

# Model String Hygiene

A retired model name hardcoded in several places once broke a whole tool.

- Keep each provider's model name in ONE constant or config entry. Never repeat the string.
- Before changing a model name, verify it against the provider's current model list (API or official docs) and quote the source in the PR body.
- When changing a name, search the whole repo for the old string and replace every occurrence, including docs and tests.
- On a model-not-found or deprecation error, fail with a clear message that includes the provider and the model name.
- Do not silently fall back to another provider. A paid fallback is forbidden (see `zero-cost-gate`).
- Keep API keys out of the repo and out of logs. Use the secret store.
- State the free-tier rate limits next to the constant.
