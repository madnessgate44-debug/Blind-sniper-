# Blind Sniper Source Library

Source-preserving imports selected from public harness repositories. Imported files are reference assets, not automatically executable tools. Host-specific commands, MCP names, shell scripts, CI workflows and runtime assumptions must be adapted and verified before activation.

| Source | License | Imported assets |
|---|---|---|
| https://github.com/0xenzyme/agent-harness | MIT | Intake, execute and init skills; worker-runner contract; Codex-native execution reference |
| https://github.com/SUNRNEHUI/agent-harness | MIT | Agent Harness skill; task-spec and subagent-task templates |
| https://github.com/os-factory/har | Apache-2.0 | Factory-line and new-plugin skills |

Each pack preserves upstream paths and includes its upstream LICENSE file. Retain attribution and license texts when adapting or redistributing.

## Not copied verbatim
https://github.com/mendelevium/claude-code-config was inspected, but GitHub reports no declared license. Its files are not copied without permission or a confirmed applicable license. Its design patterns may inform independently authored compatible files, with attribution.

## Activation rules
1. Reference-only until host compatibility review.
2. Never run imported shell scripts, workflows or hooks merely because they exist.
3. Translate Claude Code-specific hooks, agents, MCP config and commands into explicit Blind Sniper adapters.
4. External calls, browser access, secrets, deployments and paid resources remain permission-gated.
5. Record upstream revision, license, adaptations and validation in the runtime registry.

## Reference identity reconciliation — 2026-11-09

The previously selected URL `https://github.com/mattzcarey/claude-code-agent-framework` does not resolve: GitHub returns 404, and repository search under the `mattzcarey` owner does not find that repository. The source identity is therefore classified as **unavailable / invalid reference**; no files were imported from it.

Nearby repositories were inspected but are not interchangeable replacements:

- [`mattzcarey/crossroads`](https://github.com/mattzcarey/crossroads) — AI-agent orchestration on Cloudflare Durable Objects; MPL-2.0. It is a Cloudflare-specific runtime project, not the named Claude Code framework.
- [`mattzcarey/shippie`](https://github.com/mattzcarey/shippie) — extendable code-review and QA agent; not a general agent framework.
- [`mattzcarey/claude-code-action`](https://github.com/mattzcarey/claude-code-action) — Claude Code GitHub action for PRs/issues; not the requested framework.

None is substituted automatically. If one of these was the intended fourth reference, the exact repository must be explicitly selected before any adoption or import.
