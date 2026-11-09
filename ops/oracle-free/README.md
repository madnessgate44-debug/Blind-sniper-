# Oracle Always Free persistent browser host

**OWNER STATUS: UNUSABLE.** This option requires payment-card verification at account signup. The Owner's hard constraint is no card, no payment and no paid plan. Do not ask the Owner to register, do not recommend this service as a usable hosting path, and do not initiate provisioning. This document is retained only as a technical record, not an actionable hosting recommendation.

## Technical background only — not an approved option

Oracle lists Always Free Ampere A1 resources: 1,500 OCPU-hours and 9,000 GB-hours monthly (equivalent to 2 OCPUs and 12 GB RAM total), plus up to two AMD micro VMs. This is the strongest $0 recurring-cost VM option found for a persistent browser host. It is not an uptime guarantee: Oracle may reclaim an Always Free compute instance after a 7-day period when CPU, network and (for A1) memory utilization all remain below its published thresholds. A lightly used browser runner can therefore be reclaimed. Sources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm and https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm.

**Important constraints**
- Oracle account signup normally requires a credit/debit card and phone for verification; Oracle may place a temporary authorization hold (typically removed within 3–5 days). Oracle states the card is not charged unless the account is upgraded. If you will not provide a card, this cloud-host option is unavailable.
- Keep all compute and storage within Always Free limits. Do not upgrade to Pay As You Go. Use OCI budget/compartment quotas where available.
- A1 capacity can be unavailable in a home region. Oracle may show an out-of-host-capacity error.
- Oracle can reclaim idle Always Free compute. A browser runner with little real workload may not remain online indefinitely; do not claim guaranteed persistence.
- This is a self-managed VM: OS patching, firewall, backups, monitoring and runner maintenance are the owner's responsibility.
- This host bootstrap does not provision an Oracle account or VM and does not claim that a host is online.

## Deployment

1. Create an Oracle Cloud Free Tier account and select a home region. Confirm the region offers the Always Free Ampere A1 shape.
2. Create one Ubuntu 22.04 or 24.04 ARM64 VM using no more than 2 OCPUs and 12 GB RAM total, with boot volume within Always Free limits. Oracle documents a 47 GB minimum boot volume and 200 GB total Always Free block storage. Do not select paid shapes or paid add-ons.
3. Configure ingress to expose no browser debugging/CDP port publicly. SSH should be restricted to the owner's IP; the GitHub runner makes outbound HTTPS connections.
4. SSH to the VM and upload/run `bootstrap-self-hosted-runner.sh` as root.
5. In GitHub, create a short-lived **repository runner registration token** for `madnessgate44-debug/Blind-sniper-` and enter it at the script prompt. The token is not written into this repository or a plaintext file.
6. Confirm the runner appears with label `blind-sniper-browser` in repository Settings → Actions → Runners.
7. Add repository variable `BLIND_SNIPER_SELF_HOSTED_ENABLED=true`, then manually run the **Blind Sniper Browser Adapter** workflow with `workflow_dispatch`. Its two optional self-hosted jobs open a browser in job 1 and verify the same live page in job 2. The variable defaults to absent/false, so no PR or push job waits for an unprovisioned runner.

## Runtime contract

The bootstrap installs Node.js 22, `agent-browser@0.41.2`, the official GitHub Actions Linux ARM64 runner, and the published Chrome for Testing Linux ARM64 binary. Important: the pinned agent-browser CLI supports Linux ARM64, but its own bundled Chrome installer rejects Linux aarch64; the bootstrap therefore downloads the official `linux-arm64` Chrome asset directly and supplies `AGENT_BROWSER_EXECUTABLE_PATH`. It sets:
- `BLIND_SNIPER_BROWSER_STATE_DIR=/var/lib/blind-sniper/browser` — survives job workspace cleanup.
- `BLIND_SNIPER_BROWSER_IDLE_TIMEOUT=0` — browser daemon is not idled out by the CLI.
- Empty domain allowlist — deny all until a workflow supplies an explicit per-task allowlist.
- `BLIND_SNIPER_BROWSER_WRITE_APPROVED=0` — no write actions until a separately authorized job sets approval and reference.

The browser adapter and dispatcher must be invoked with the task ledger and active owner lease. The ARM64 Chrome binary has not yet been smoke-tested on a provisioned Oracle VM; the host capability remains unverified until that happens. Never expose the Chrome CDP port, browser dashboard, or MCP stdio endpoint directly to the public internet. A future remote MCP gateway must authenticate every request and invoke the native lease-gated dispatcher; a raw agent-browser MCP endpoint is not an acceptable production boundary.

## What remains owner-dependent

The script cannot create the Oracle tenancy, verify identity/card, create the VM, open SSH, or mint the GitHub runner token. These are account-level actions requiring the owner's participation. After runner registration, run the optional two-job self-hosted persistence acceptance. It is gated by the repository variable `BLIND_SNIPER_SELF_HOSTED_ENABLED=true` and manual `workflow_dispatch`; it verifies the same page remains in the same Chromium session across two separate GitHub Actions jobs. Do not mark the persistent-host capability VERIFIED until that test passes on the actual Oracle VM.

## Rollback

Stop and remove the runner with `/opt/actions-runner/svc.sh stop` and `/opt/actions-runner/config.sh remove --token <fresh removal token>`. Delete the VM and attached resources from OCI only after exporting any required evidence and browser state. Deleting the VM permanently deletes its local state unless backed up.
