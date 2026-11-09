# Blind Sniper Source Library

Source-preserving imports selected from public harness repositories. Imported files are reference assets, not automatically executable tools. Host-specific commands, MCP names, shell scripts, CI workflows and runtime assumptions must be adapted and verified before activation.

| Source | License evidence | Imported assets |
|---|---|---|
| https://github.com/0xenzyme/agent-harness | MIT | Intake, execute and init skills; worker-runner contract; Codex-native execution reference |
| https://github.com/SUNRNEHUI/agent-harness | MIT | Agent Harness skill; task-spec and subagent-task templates |
| https://github.com/os-factory/har | Apache-2.0 | Factory-line and new-plugin skills |

Each imported pack preserves upstream paths and includes its upstream LICENSE file. Retain attribution and license texts when adapting or redistributing.

## Inspected but not imported

### Claude Code Showcase / Mendelevium fork

- https://github.com/ChrisWiles/claude-code-showcase
- https://github.com/mendelevium/claude-code-config

These are one source lineage, not two independent frameworks: Mendelevium identifies Showcase as its parent fork, and both currently resolve to the same commit and Git tree. Both GitHub repository API records report `license: null`; neither repository root contains a `LICENSE` file. The README contains the statement `MIT - Use this as a template for your own projects`, but no complete MIT license text is present in the repository root. This is recorded as **license evidence requiring clarification**, not as a verified standard MIT grant. Do not copy or redistribute their code verbatim until the applicable license is confirmed or permission is obtained. Their architecture patterns may inform independently authored compatible files, with attribution.

### Ralph

- https://github.com/snarktank/ralph

GitHub reports MIT license metadata and the repository contains a root `LICENSE` file with the MIT License text. The source is eligible for selective adaptation subject to preserving the copyright and license notice. Its execution loop and permission model still require a separate safety/compatibility review; the presence of an MIT license is not runtime approval.

## Mattzcarey reference identity

The previously selected URL `https://github.com/mattzcarey/claude-code-agent-framework` returns GitHub 404. A repository search under the `mattzcarey` owner did not find that exact repository. No files were imported from the missing reference.

Nearby repositories are not interchangeable replacements:

- [`mattzcarey/shippie`](https://github.com/mattzcarey/shippie) — extendable code-review and QA agent; GitHub reports MIT metadata and its package manifest declares MIT. It is not the named general Claude Code framework.
- [`mattzcarey/agents`](https://github.com/mattzcarey/agents) — fork of `cloudflare/agents`, a Cloudflare Durable Objects agent SDK; not a Claude Code configuration framework.
- [`mattzcarey/crossroads`](https://github.com/mattzcarey/crossroads) — Cloudflare Durable Objects orchestration project; not the named Claude Code framework.
- [`mattzcarey/claude-code-action`](https://github.com/mattzcarey/claude-code-action) — Claude Code GitHub action for PRs/issues; not the requested general framework.

None is substituted automatically. The intended fourth reference remains **unresolved** until its exact repository URL or name is confirmed.

## Activation rules

1. Reference-only until host compatibility review.
2. Never run imported shell scripts, workflows or hooks merely because they exist.
3. Translate Claude Code-specific hooks, agents, MCP config and commands into explicit Blind Sniper adapters.
4. External calls, browser access, secrets, deployments and paid resources remain permission-gated.
5. Record upstream revision, license evidence, adaptations and validation in the runtime registry.
6. Treat GitHub license metadata, a root LICENSE file, README license claims and explicit permission as distinct evidence fields; do not collapse them into one status.
