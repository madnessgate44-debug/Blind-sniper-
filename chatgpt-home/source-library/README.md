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

These are one source lineage, not two independent frameworks: Mendelevium identifies Showcase as its parent fork, and both resolved to the same commit and Git tree at the inspected snapshot. Both GitHub repository API records report `license: null`; neither repository root contains a `LICENSE` file. The README contains the statement `MIT - Use this as a template for your own projects`, but no complete MIT license text is present in the repository root. This is **license evidence requiring clarification**, not a verified standard MIT grant. Do not copy or redistribute their code verbatim until the applicable license is confirmed or permission is obtained. Their architecture patterns may inform independently authored compatible files, with attribution.

### Ralph

- https://github.com/snarktank/ralph

GitHub reports MIT license metadata and the repository contains a root `LICENSE` file with the MIT License text. The source is eligible for selective adaptation subject to preserving the copyright and license notice. Its execution loop and permission model still require a separate safety/compatibility review; the presence of an MIT license is not runtime approval. Blind Sniper's native task ledger, approval gates and verification rules remain authoritative; do not import the runner's permission-bypass defaults.

## Unavailable reference — explicitly excluded

The previously selected URL `https://github.com/mattzcarey/claude-code-agent-framework` returned GitHub 404 and exact-name search did not establish the repository identity. The Owner has accepted that this reference will not be identified. It is therefore classified **UNAVAILABLE — EXCLUDED — NOT A PROJECT DEPENDENCY** for the Blind Sniper architecture. Do not continue searching, substitute a nearby repository, or block implementation on this reference. No files were imported from it.

Historical audit notes may preserve the original lookup result. They do not reopen this dependency.

## Activation rules

1. Reference-only until host compatibility review.
2. Never run imported shell scripts, workflows or hooks merely because they exist.
3. Translate Claude Code-specific hooks, agents, MCP config and commands into explicit Blind Sniper adapters.
4. External calls, browser access, secrets, deployments and paid resources remain permission-gated.
5. Record upstream revision, license evidence, adaptations and validation in the runtime registry.
6. Treat GitHub license metadata, a root LICENSE file, README license claims and explicit permission as distinct evidence fields; do not collapse them into one status.
