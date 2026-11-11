# Blind Sniper — GitHub and Vercel hosting boundary

**Status:** Vercel HTTP host deployed and health-smoke-tested; task execution is deliberately disabled.

## Platform responsibilities

- **GitHub repository:** canonical public source, code review and release history. Never store private task payloads, credentials, user data or execution receipts here.
- **GitHub Actions:** bounded, event-driven Python execution and verification. Scheduled workflows are short-lived jobs, not resident workers. The existing native executor and private GitHub Contents CAS ledger remain the execution foundation.
- **Vercel Functions:** hosted HTTP ingress and lightweight API endpoints. Python Functions run as bounded serverless invocations; they are not an always-on daemon.
- **Private continuity repository:** task payloads, durable receipts and cross-run CAS state remain in the already owner-approved private store. This public repository must not contain those records.

## Initial deployment

`api/health.py` exposes a read-only `GET /api/health` endpoint. Production project: `blind-sniper-runtime` (`prj_AJpyM5PkAxfmeb4KQCZ7hlBgMZEi`), latest Git-linked production deployment `dpl_HVwBwRYfa9CRcziujcyzZAiX6zPS` (source commit `284b80b57c3d77a1099bb329bc0486323db3a2c9`), alias `https://blind-sniper-runtime.vercel.app`, region `fra1`. Live smoke result: HTTP 200 with JSON status `ok`, `worker=not_activated` and `task_execution_enabled=false`. The route does not read secrets, enqueue tasks, invoke models, mutate GitHub, or expose private state. A later `main` push automatically triggered this Git-sourced production deployment, confirming the repository-to-Vercel deployment link.

`pyproject.toml` explicitly selects `api.health:handler` as the Python runtime entrypoint; this is required because the repository contains multiple Python scripts and Vercel's auto-discovery did not select the function. `vercel.json` limits this health function to 10 seconds. Project deployment SSO protection is disabled because this endpoint contains only non-sensitive health metadata; do not add private endpoints without first implementing authentication and access controls. No cron schedule is configured. The Vercel Hobby plan is limited to daily cron execution and has bounded function duration; it is therefore not the high-frequency worker scheduler. GitHub Actions remains the preferred trigger for bounded execution. Do not claim continuous residency.

## Activation gates — intentionally closed

Do not enable task intake or execution until all are verified:

1. A private durable task/payload store is configured and its repository metadata is confirmed private at runtime.
2. A least-privilege credential is already available to the runtime through the platform's secret manager; do not create, print, rotate or mutate credentials as part of this adapter.
3. The native model provider is configured and a real bounded model round trip succeeds.
4. The executor uses the existing native agent/tool allowlists, task leases, idempotency and correlated receipts.
5. A single end-to-end task is executed through the real trigger, with logs, state transitions and recovery evidence inspected.

No authenticated browser session is persisted by this Vercel adapter. Browser work remains a separate bounded native-browser acceptance gate.

## Plan and compliance constraints

The discovered Vercel team is on Hobby. Keep use within free limits and personal/non-commercial restrictions; do not upgrade, provision paid resources or introduce billing. Confirm current plan limits before adding schedules or long-running work. A successful Vercel deployment proves only that the HTTP function is hosted, not that Blind Sniper autonomy is active.
