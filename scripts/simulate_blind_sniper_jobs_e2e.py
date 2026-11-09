#!/usr/bin/env python3
"""Deterministic end-to-end simulation of the Blind Sniper scheduled-jobs pipeline.

This is a CI simulation, not a real scheduler. It models the
continuous-autonomy pipeline (receive -> deduplicate -> dispatch -> retry with
loop breaker -> persist state -> deliver) across a fixed set of scheduled ticks,
and it exercises the real local task ledger for the dispatch lease and the
append-only audit chain.

The simulation never contacts a network, never spawns an agent or model, and
never claims a real background scheduler exists: those are recorded as false in
the receipt. See chatgpt-home/runtime/E2E_SIMULATION.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_ledger import TaskLedger  # noqa: E402

TICK_SECONDS = 7200
BASE_TIME = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
MAX_CONSECUTIVE_FAILURES = 3

JOBS: list[dict[str, Any]] = [
    {"job_id": "job-audit", "name": "daily-audit", "schedule": "0 9 * * *", "interval_seconds": 86400},
    {"job_id": "job-loop", "name": "two-hour-loop", "schedule": "0 */2 * * *", "interval_seconds": TICK_SECONDS},
]

# (tick, job, task, event_key, attempt outcomes). attempt outcomes are "PASS"/"FAIL".
EVENTS: list[dict[str, Any]] = [
    {"tick": 0, "job": "job-audit", "task": "T1", "key": "evt-T1-1", "attempts": ["PASS"]},
    {"tick": 1, "job": "job-loop", "task": "T2", "key": "evt-T2-1", "attempts": ["FAIL", "PASS"]},
    {"tick": 1, "job": "job-loop", "task": "T1", "key": "evt-T1-1", "attempts": ["PASS"]},  # duplicate redelivery
    {"tick": 2, "job": "job-loop", "task": "T3", "key": "evt-T3-1", "attempts": ["FAIL", "FAIL", "FAIL"]},
]


class SimulationFailure(RuntimeError):
    """A deterministic simulation acceptance check failed."""


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tick_time(tick: int) -> datetime:
    return BASE_TIME + timedelta(seconds=tick * TICK_SECONDS)


def run(output_dir: Path) -> dict[str, Any]:
    commit_sha = os.environ.get("GITHUB_SHA", "")
    workflow_run_id = os.environ.get("GITHUB_RUN_ID", "")
    if len(commit_sha) != 40 or not workflow_run_id.isdigit():
        raise SimulationFailure("Requires GitHub Actions GITHUB_SHA and GITHUB_RUN_ID; fails closed elsewhere.")

    with tempfile.TemporaryDirectory(prefix="blind-sniper-jobs-") as temp:
        work = Path(temp)
        ledger_file = work / "job-events.jsonl"
        ledger = TaskLedger(ledger_file)

        jobs = {job["job_id"]: {**job, "next_run_at": BASE_TIME, "consecutive_failures": 0,
                                "loop_breaker_tripped": False, "runs": 0, "skips": 0} for job in JOBS}
        seen_keys: set[str] = set()
        events_by_tick: dict[int, list[dict[str, Any]]] = {}
        for event in EVENTS:
            events_by_tick.setdefault(event["tick"], []).append(event)

        # Run one tick past the last event so a tripped loop breaker is observably skipped.
        max_tick = (max(events_by_tick) if events_by_tick else 0) + 1
        stats = {"ticks": 0, "jobs_fired": 0, "jobs_skipped": 0, "events_received": 0,
                 "events_deduplicated": 0, "tasks_dispatched": 0, "tasks_completed": 0,
                 "tasks_failed": 0, "retries": 0, "loop_breakers_tripped": 0}
        deliveries: list[dict[str, Any]] = []

        def record(task_id: str, event_type: str, payload: dict[str, Any], key: str) -> None:
            ledger.append(task_id=task_id, event_type=event_type, payload=payload, idempotency_key=key)

        for tick in range(max_tick + 1):
            stats["ticks"] += 1
            instant = tick_time(tick)
            for job_id, job in jobs.items():
                if instant < job["next_run_at"]:
                    continue
                stats["jobs_fired"] += 1
                job["runs"] += 1
                job["next_run_at"] = instant + timedelta(seconds=job["interval_seconds"])

                if job["loop_breaker_tripped"]:
                    job["skips"] += 1
                    stats["jobs_skipped"] += 1
                    record(job_id, "JOB_SKIPPED_BREAKER_TRIPPED",
                           {"job_id": job_id, "tick": tick, "consecutive_failures": job["consecutive_failures"]},
                           f"{job_id}:skip:{tick}")
                    continue

                for event in events_by_tick.get(tick, []):
                    if event["job"] != job_id:
                        continue
                    stats["events_received"] += 1
                    task_id = event["task"]
                    record(task_id, "JOB_EVENT_RECEIVED",
                           {"job_id": job_id, "event_key": event["key"], "tick": tick},
                           f"{event['key']}:received:{tick}")

                    if event["key"] in seen_keys:
                        stats["events_deduplicated"] += 1
                        record(task_id, "JOB_EVENT_DEDUPLICATED",
                               {"job_id": job_id, "event_key": event["key"], "tick": tick},
                               f"{event['key']}:dedupe:{tick}")
                        continue
                    seen_keys.add(event["key"])

                    # Dispatch: the real ledger grants one execution lease and the
                    # task may only run under that owner. A competing owner is denied.
                    owner = f"{job_id}-runner"
                    claim = ledger.claim_task(task_id=task_id, owner_id=owner, lease_seconds=600,
                                              idempotency_key=f"{event['key']}:claim", now=instant)
                    if not claim.get("claimed"):
                        raise SimulationFailure(f"Dispatch lease for {task_id} was not granted.")
                    competing = ledger.claim_task(task_id=task_id, owner_id="competing-runner", lease_seconds=600,
                                                  idempotency_key=f"{event['key']}:claim-competing", now=instant)
                    if competing.get("claimed"):
                        raise SimulationFailure(f"Competing lease for {task_id} was not denied.")
                    record(task_id, "JOB_DISPATCHED",
                           {"job_id": job_id, "event_key": event["key"], "lease_owner": owner, "tick": tick},
                           f"{event['key']}:dispatched")
                    stats["tasks_dispatched"] += 1

                    outcome = "FAIL"
                    for index, attempt in enumerate(event["attempts"]):
                        if index > 0:
                            stats["retries"] += 1
                        if attempt == "PASS":
                            outcome = "PASS"
                            record(task_id, "JOB_ATTEMPT_SUCCEEDED",
                                   {"job_id": job_id, "attempt": index + 1, "tick": tick},
                                   f"{event['key']}:attempt:{index + 1}")
                            break
                        job["consecutive_failures"] += 1
                        record(task_id, "JOB_ATTEMPT_FAILED",
                               {"job_id": job_id, "attempt": index + 1, "consecutive_failures": job["consecutive_failures"]},
                               f"{event['key']}:attempt:{index + 1}")
                        if job["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                            job["loop_breaker_tripped"] = True
                            stats["loop_breakers_tripped"] += 1
                            record(task_id, "JOB_BREAKER_TRIPPED",
                                   {"job_id": job_id, "tick": tick, "consecutive_failures": job["consecutive_failures"]},
                                   f"{event['key']}:breaker")
                            break

                    if outcome == "PASS":
                        job["consecutive_failures"] = 0
                        digest = sha256_text(f"{task_id}:{event['key']}:{workflow_run_id}")
                        record(task_id, "JOB_DELIVERED",
                               {"job_id": job_id, "tick": tick, "delivery_sha256": digest},
                               f"{event['key']}:delivered")
                        stats["tasks_completed"] += 1
                        deliveries.append({"task_id": task_id, "job_id": job_id, "tick": tick,
                                           "delivery_sha256": digest})
                    else:
                        stats["tasks_failed"] += 1

                    ledger.release_task(task_id=task_id, owner_id=owner,
                                        idempotency_key=f"{event['key']}:release", now=instant)

        # Re-reading the ledger validates the entire hash chain and sequence.
        history = ledger.events()
        if not history:
            raise SimulationFailure("Job ledger is empty.")
        for index, row in enumerate(history, 1):
            if row["seq"] != index:
                raise SimulationFailure("Job ledger sequence is not contiguous.")

        tripped = [job_id for job_id, job in jobs.items() if job["loop_breaker_tripped"]]
        if stats["events_deduplicated"] != 1:
            raise SimulationFailure(f"Expected 1 deduplicated event, got {stats['events_deduplicated']}.")
        if stats["retries"] != 3:
            raise SimulationFailure(f"Expected 3 retries, got {stats['retries']}.")
        if stats["loop_breakers_tripped"] != 1 or tripped != ["job-loop"]:
            raise SimulationFailure(f"Loop breaker state unexpected: tripped={tripped}.")
        if stats["jobs_skipped"] != 1:
            raise SimulationFailure(f"Expected 1 breaker skip, got {stats['jobs_skipped']}.")
        if stats["tasks_completed"] != 2 or stats["tasks_failed"] != 1:
            raise SimulationFailure("Task outcome counts do not match the deterministic plan.")
        # job-audit is daily: it must fire once across the short tick window and
        # must not fire again before its interval elapses.
        if jobs["job-audit"]["runs"] != 1:
            raise SimulationFailure(f"Daily job fired {jobs['job-audit']['runs']} times, expected 1.")
        if jobs["job-loop"]["runs"] != 4:
            raise SimulationFailure(f"Loop job fired {jobs['job-loop']['runs']} times, expected 4.")

        receipt = {
            "schema_version": "1.0.0",
            "status": "PASS",
            "execution_mode": "SIMULATION_ONLY",
            "real_scheduler_present": False,
            "scheduler_kind": "deterministic_test_harness_not_a_real_scheduler",
            "actual_agent_spawned": False,
            "external_network_calls": 0,
            "commit_sha": commit_sha,
            "workflow_run_id": workflow_run_id,
            "pipeline": ["receive", "deduplicate", "dispatch", "retry_with_loop_breaker", "persist_state", "deliver"],
            "jobs": [{"job_id": job["job_id"], "name": job["name"], "schedule": job["schedule"],
                      "runs": job["runs"], "skips": job["skips"],
                      "loop_breaker_tripped": job["loop_breaker_tripped"]} for job in jobs.values()],
            "stats": stats,
            "deliveries": deliveries,
            "ledger_event_count": len(history),
            "ledger_final_hash": history[-1]["event_hash"],
            "ledger_hash_chain_verified": True,
            "reviewer_kind": "deterministic_test_harness_not_human_or_model_agent",
        }
        write_json(output_dir / "jobs-receipt.json", receipt)
        write_json(output_dir / "jobs-state.json", {job_id: {k: v for k, v in job.items() if k != "next_run_at"}
                                                    | {"next_run_at": job["next_run_at"].isoformat()}
                                                    for job_id, job in jobs.items()})
        write_json(output_dir / "job-ledger-history.json", history)
        shutil.copy2(ledger_file, output_dir / "job-events.jsonl")

    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Directory for CI simulation artifacts")
    args = parser.parse_args()
    try:
        receipt = run(Path(args.output_dir).resolve())
    except SimulationFailure as exc:
        print(f"JOBS E2E SIMULATION FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
