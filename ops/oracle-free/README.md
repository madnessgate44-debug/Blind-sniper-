# Oracle Always Free persistent browser host

## Why this is the selected $0 option

Oracle lists Always Free compute resources including Ampere A1: 1,500 OCPU-hours and 9,000 GB-hours monthly (equivalent to 2 OCPUs and 12 GB RAM), plus two AMD micro VMs. The free compute quota can support a persistent ARM64 host, unlike GitHub-hosted runners which are ephemeral per job. Oracle's free-tier FAQ says Always Free resources remain available after the trial, but idle compute may be reclaimed under its published utilization test. Sources: Oracle Free Tier and Always Free resource documentation.

**Important constraints**
- Oracle account signup normally requires a payment card for verification; Oracle may place a temporary verification hold. It states the card is not charged unless the account is upgraded.
- Keep all compute and storage within Always Free limits. Do not upgrade to Pay As You Go. Use OCI budget/compartment quotas where available.
- A1 capacity can be unavailable in a home region. Oracle may show an out-of-host-capacity error.
- This is a self-managed VM: OS patching, firewall, backups, monitoring and runner maintenance are the owner's responsibility.
- This host bootstrap does not provision an Oracle account or VM and does not claim that a host is online.

## Deployment

1. Create an Oracle Cloud Free Tier account and select a home region. Confirm the region offers the Always Free Ampere A1 shape.
2. Create one Ubuntu 22.04 or 24.04 ARM64 VM using no more than 2 OCPUs and 12 GB RAM total, with boot volume within Always Free limits. Do not select paid shapes or paid add-ons.
3. Configure ingress to expose no browser debugging/CDP port publicly. SSH should be restricted to the owner's IP; the GitHub runner makes outbound HTTPS connections.
4. SSH to the VM and upload/run `bootstrap-self-hosted-runner.sh` as root.
5. In GitHub, create a short-lived **repository runner registration token** for `madnessgate44-debug/Blind-sniper-` and enter it at the script prompt. The token is not written into this repository or a plaintext file.
6. Confirm the runner appears with label `blind-sniper-browser` in repository Settings → Actions → Runners.

## Runtime contract

The bootstrap installs Node.js 22, `agent-browser@0.41.2`, the official GitHub Actions Linux ARM64 runner, and the published Chrome for Testing Linux ARM64 binary. Important: the pinned agent-browser CLI supports Linux ARM64, but its own bundled Chrome installer rejects Linux aarch64; the bootstrap therefore downloads the official `linux-arm64` Chrome asset directly and supplies `AGENT_BROWSER_EXECUTABLE_PATH`. It sets:
- `BLIND_SNIPER_BROWSER_STATE_DIR=/var/lib/blind-sniper/browser` — survives job workspace cleanup.
- `BLIND_SNIPER_BROWSER_IDLE_TIMEOUT=0` — browser daemon is not idled out by the CLI.
- Empty domain allowlist — deny all until a workflow supplies an explicit per-task allowlist.
- `BLIND_SNIPER_BROWSER_WRITE_APPROVED=0` — no write actions until a separately authorized job sets approval and reference.

The browser adapter and dispatcher must be invoked with the task ledger and active owner lease. The ARM64 Chrome binary has not yet been smoke-tested on a provisioned Oracle VM; the host capability remains unverified until that happens. Never expose the Chrome CDP port, browser dashboard, or MCP stdio endpoint directly to the public internet. A future remote MCP gateway must authenticate every request and invoke the native lease-gated dispatcher; a raw agent-browser MCP endpoint is not an acceptable production boundary.

## What remains owner-dependent

The script cannot create the Oracle tenancy, verify identity/card, create the VM, open SSH, or mint the GitHub runner token. These are account-level actions requiring the owner's participation. After runner registration, the repository workflow still needs an explicit `runs-on: [self-hosted, linux, ARM64, blind-sniper-browser]` deployment/acceptance job and a controlled two-job session-persistence test before the persistent-host capability can be marked VERIFIED.

## Rollback

Stop and remove the runner with `/opt/actions-runner/svc.sh stop` and `/opt/actions-runner/config.sh remove --token <fresh removal token>`. Delete the VM and attached resources from OCI only after exporting any required evidence and browser state. Deleting the VM permanently deletes its local state unless backed up.
