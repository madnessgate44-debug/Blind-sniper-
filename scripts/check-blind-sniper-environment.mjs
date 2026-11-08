#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const required = [
  "chatgpt-home/ENVIRONMENT_MANIFEST.md",
  "chatgpt-home/skills/README.md",
  "chatgpt-home/skills/github-workspace/SKILL.md",
  "chatgpt-home/skills/web-research/SKILL.md",
  "chatgpt-home/skills/browser-operations/SKILL.md",
  "chatgpt-home/skills/agent-dispatch/SKILL.md",
  "chatgpt-home/skills/workflow-authoring/SKILL.md",
  "chatgpt-home/skills/test-and-evidence/SKILL.md",
  "chatgpt-home/skills/security-and-permissions/SKILL.md",
  "chatgpt-home/skills/memory-and-continuity/SKILL.md",
  "chatgpt-home/skills/codex-environment-maintenance/SKILL.md",
  "chatgpt-home/agents/researcher.md",
  "chatgpt-home/agents/planner.md",
  "chatgpt-home/agents/engineer.md",
  "chatgpt-home/agents/reviewer.md",
  "chatgpt-home/agents/qa-verifier.md",
  "chatgpt-home/agents/recovery.md",
  "chatgpt-home/agents/watcher.md",
  "chatgpt-home/agents/shadow.md",
  "chatgpt-home/agents/release-manager.md",
  "chatgpt-home/tools/TOOL_REGISTRY.md",
  "chatgpt-home/workflows/session-boot.md",
  "chatgpt-home/workflows/task-lifecycle.md",
  "chatgpt-home/workflows/agent-handoff.md",
  "chatgpt-home/workflows/session-close.md",
  "chatgpt-home/workflows/release-gate.md",
  "chatgpt-home/templates/AGENT_TASK.md",
  "chatgpt-home/templates/VERIFICATION_LEDGER.md",
  "chatgpt-home/templates/REVIEW_REPORT.md",
  "chatgpt-home/templates/RUN_RECEIPT.md",
  "chatgpt-home/runtime/ADAPTER_CONTRACT.md",
  "chatgpt-home/hooks/HOOKS_AND_GUARDS.md",
  "chatgpt-home/mcp/MCP_AND_BROWSER_INTEGRATIONS.md",
  "chatgpt-home/config/base.config.toml.example",
  "chatgpt-home/config/blind-sniper.config.toml.example",
  "chatgpt-home/config/research.config.toml.example",
  "chatgpt-home/config/engineering.config.toml.example",
  "chatgpt-home/config/review.config.toml.example",
  "chatgpt-home/config/recovery.config.toml.example"
];

const errors = [];
for (const rel of required) {
  if (!fs.existsSync(path.join(root, rel))) errors.push(`MISSING: ${rel}`);
}
const skillFiles = required.filter(p => p.startsWith("chatgpt-home/skills/") && p.endsWith("SKILL.md"));
for (const rel of skillFiles) {
  if (!fs.existsSync(path.join(root, rel))) continue;
  const content = fs.readFileSync(path.join(root, rel), "utf8");
  const frontmatter = content.match(/^---\n([\s\S]*?)\n---\n/);
  if (!frontmatter) { errors.push(`NO_FRONTMATTER: ${rel}`); continue; }
  for (const key of ["name:", "description:", "triggers:", "risk:", "required_tools:"]) {
    if (!frontmatter[1].split("\n").some(line => line.startsWith(key))) errors.push(`MISSING_METADATA ${key} in ${rel}`);
  }
  for (const heading of ["## Purpose", "## Prerequisites", "## Permissions", "## Procedure", "## Evidence", "## Failure handling", "## Completion criteria"]) {
    if (!content.includes(heading)) errors.push(`MISSING_SECTION ${heading} in ${rel}`);
  }
}
const agentFiles = required.filter(p => p.startsWith("chatgpt-home/agents/") && p.endsWith(".md") && !p.endsWith("README.md"));
for (const rel of agentFiles) {
  if (!fs.existsSync(path.join(root, rel))) continue;
  const content = fs.readFileSync(path.join(root, rel), "utf8");
  for (const marker of ["Mission:", "Inputs:", "Tools:", "Output:", "Authority:", "Prohibited:", "Acceptance:"]) {
    if (!content.includes(marker)) errors.push("MISSING_AGENT_CONTRACT " + marker + " in " + rel);
  }
}
const workflowFiles = required.filter(p => p.startsWith("chatgpt-home/workflows/") && p.endsWith(".md"));
for (const rel of workflowFiles) {
  if (!fs.existsSync(path.join(root, rel))) continue;
  const content = fs.readFileSync(path.join(root, rel), "utf8");
  if (content.trim().length < 200) errors.push("WORKFLOW_TOO_SHORT: " + rel);
}
const configFiles = required.filter(p => p.startsWith("chatgpt-home/config/") && p.endsWith(".toml.example"));
for (const rel of configFiles) {
  if (!fs.existsSync(path.join(root, rel))) continue;
  const content = fs.readFileSync(path.join(root, rel), "utf8");
  if (!content.includes('approval_policy = "on-request"')) errors.push("UNSAFE_OR_MISSING_APPROVAL_DEFAULT: " + rel);
  if (!/sandbox_mode = "(read-only|workspace-write)"/.test(content)) errors.push("UNSAFE_OR_MISSING_SANDBOX_DEFAULT: " + rel);
  if (/danger-full-access|dangerously-bypass-approvals-and-sandbox/.test(content)) errors.push("DANGEROUS_SANDBOX_SETTING: " + rel);
}
const manifests = [
  "chatgpt-home/ENVIRONMENT_MANIFEST.md",
  "chatgpt-home/tools/TOOL_REGISTRY.md",
  "chatgpt-home/runtime/ADAPTER_CONTRACT.md"
];
for (const rel of manifests) {
  if (!fs.existsSync(path.join(root, rel))) continue;
  const content = fs.readFileSync(path.join(root, rel), "utf8");
  if (/gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}/.test(content)) {
    errors.push(`POSSIBLE_CREDENTIAL_PATTERN: ${rel}`);
  }
}
if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log("PASS: " + required.length + " required assets; " + skillFiles.length + " skill contracts; " + agentFiles.length + " agent contracts; " + workflowFiles.length + " workflows; " + configFiles.length + " safe Codex config templates; credential-pattern scan clean.");
