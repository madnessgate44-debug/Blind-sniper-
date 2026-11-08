# Workflow: Isolated Execution Line

**Adapted from:** os-factory/har factory-line and worktree model (Apache-2.0).

1. Read the line manifest and identify the next incomplete station.
2. Check workspace/slot availability and reserve one isolated worktree per worker.
3. Build waves only from independent tasks; coupled writes remain serial.
4. Execute in assigned worktrees; collect changed paths, commits and test evidence.
5. Integrate only after worker outputs are independently reviewed.
6. Run cumulative gates, including all earlier station gates.
7. Stop on a red gate. Never bypass or mark it green manually.
8. Produce a human handoff. Merge/release requires Owner authorization.
