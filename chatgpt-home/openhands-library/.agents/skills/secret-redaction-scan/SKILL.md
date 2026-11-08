---
name: secret-redaction-scan
description: "This skill should be used before any git push of data you did not write by hand (exports, logs, archives), or when the user asks to \"scan for secrets\", \"redact credentials\", or mentions push protection or leaks."
triggers:
- secret
- redact
- credential
- push protection
- leak
---

# Secret Redaction Scan

Run this before every `git push` that includes data you did not write by hand (exports, logs, fixtures, archives).

## Patterns that actually fired
- Fernet tokens: `gAAAAA...`
- OpenAI-style keys: `sk-...`
- GitHub tokens: `ghp_`, `gho_`, `ghu_`, `github_pat_`
- Tokens embedded in URLs: `https://<token>@github.com`
- Private keys: `-----BEGIN ... PRIVATE KEY-----`
- Gemini keys: `AQ.<40+ chars>` and `AIza...`

## Sweep commands
```bash
git grep -nE '(gAAAAA|sk-|ghp_|gho_|ghu_|github_pat_|AIza|AQ\.[A-Za-z0-9_-]{40,}|BEGIN [A-Z ]*PRIVATE KEY)' -- .
find . -name '*.gz' -exec sh -c 'zcat "$1" 2>/dev/null | grep -nE "gAAAAA|sk-|ghp_|AIza|AQ\.[A-Za-z0-9_-]{40,}" >/dev/null && echo "LEAK: $1"' _ {} \;
```

## Rules
- Redact in BOTH raw and rendered forms; a redacted transcript with a raw JSON sidecar still leaks.
- Never echo a secret value. The environment auto-exports referenced keys, so use them in place.
- If a leak already reached a commit, treat the credential as compromised and rotate it; do not just amend the commit.
