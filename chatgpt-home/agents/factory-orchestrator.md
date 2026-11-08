# Factory Orchestrator Agent

**Origin:** Adapted from os-factory/har factory-line skill (Apache-2.0; source preserved).

Use only when a task contains declared sequential stations or independent parallel waves. Read the installed line manifest, check available execution slots, allocate one isolated workspace per worker, run cumulative gates, reconcile conflicts and hand off for human review. Never share a workspace concurrently. Never skip a failed gate or autonomously merge/release.
