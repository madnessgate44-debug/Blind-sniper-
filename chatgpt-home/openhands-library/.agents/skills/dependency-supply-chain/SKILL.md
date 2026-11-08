---
name: dependency-supply-chain
description: "This skill should be used when the user asks to \"add a dependency\", \"upgrade a package\", \"audit dependencies\", \"fix a CVE\", or mentions lockfiles, npm audit, or supply-chain risk."
triggers:
- dependency
- cve
- npm audit
- supply chain
- upgrade
- lockfile
---

# Dependency and Supply Chain

- Justify each new dependency; prefer the standard library or existing deps.
- Pin via the lockfile; commit the lockfile.
- Run the audit (`npm audit`) and triage by reachability, not just severity.
- Read the changelog for breaking changes before upgrading a major.
- Watch for install-time scripts from untrusted packages.
