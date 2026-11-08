---
name: zero-cost-gate
description: "This skill should be used before recommending, adding or depending on any hosting, API, database, model provider or SaaS, or when the user asks to \"deploy\", \"host\", \"pick a provider\", \"add a service\", or mentions free tier, pricing, billing or a credit card."
triggers:
- free tier
- pricing
- credit card
- billing
- hosting
- deploy
- provider
---

# Zero-Cost Gate

The owner does not pay for anything and does not provide a card. A service that needs either is not an option.

- "Free" means: no card at signup, no payment, no trial that converts to paid. A free tier that asks for a card at signup counts as paid.
- Before choosing or recommending any external service, open its official pricing or signup page and quote the sentence that shows no card is required. Put the quote and URL in the PR body.
- If you cannot confirm it, mark it UNVERIFIED and do not adopt it.
- If a service asks for payment or a card mid-task, stop that path. Report it in the first line of the owner report. Offer at most two alternatives, each verified the same way.
- Never silently fall back to a paid provider when a free one fails or hits a rate limit. Fail loudly with the provider name and the limit.
- Note each free tier's rate limits and design for them.
- Add one line to the PR body: `Cost: $0 | verified <date> | source <url>`.
- Anything that could cost money later (usage-based billing, auto-upgrade) is flagged at the top of the report as an irreversible decision.
