#!/usr/bin/env bash
# Provision a $0 Oracle Always Free ARM browser host and repository-scoped GitHub Actions runner.
# Run as root on a fresh Ubuntu 22.04/24.04 ARM64 VM. Never commit the registration token.
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 2
fi
ARCH="$(dpkg --print-architecture)"
if [[ "$ARCH" != "arm64" ]]; then
  echo "Expected Oracle Ampere ARM64 (arm64); found $ARCH." >&2
  exit 2
fi
. /etc/os-release
if [[ "$ID" != "ubuntu" || ! "$VERSION_ID" =~ ^(22\.04|24\.04)$ ]]; then
  echo "Supported OS: Ubuntu 22.04 or 24.04; found $PRETTY_NAME." >&2
  exit 2
fi

read -r -p "GitHub repository URL (https://github.com/OWNER/REPO): " REPO_URL
if [[ ! "$REPO_URL" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$ ]]; then
  echo "Invalid repository URL." >&2
  exit 2
fi
read -r -s -p "Short-lived GitHub Actions runner registration token: " RUNNER_TOKEN
echo
if [[ -z "$RUNNER_TOKEN" ]]; then
  echo "Registration token is required." >&2
  exit 2
fi

RUNNER_USER="blind-sniper"
RUNNER_DIR="/opt/actions-runner"
STATE_DIR="/var/lib/blind-sniper/browser"
ENV_DIR="/etc/blind-sniper"
install -d -m 0750 "$STATE_DIR" "$ENV_DIR"
if ! id "$RUNNER_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$RUNNER_USER"
fi
chown -R "$RUNNER_USER:$RUNNER_USER" /var/lib/blind-sniper

apt-get update
apt-get install -y ca-certificates curl git jq tar gzip unzip build-essential
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs
npm install --global agent-browser@0.41.2

# Download the official latest GitHub Actions runner for Linux ARM64.
RUNNER_URL="$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r '.assets[] | select(.name | test("^actions-runner-linux-arm64-.*\\.tar\\.gz$")) | .browser_download_url' | head -n 1)"
if [[ -z "$RUNNER_URL" || "$RUNNER_URL" == "null" ]]; then
  echo "Could not find an official Linux ARM64 GitHub runner release." >&2
  exit 2
fi
install -d -o "$RUNNER_USER" -g "$RUNNER_USER" "$RUNNER_DIR"
curl -fsSL "$RUNNER_URL" -o /tmp/actions-runner.tar.gz
tar -xzf /tmp/actions-runner.tar.gz -C "$RUNNER_DIR"
chown -R "$RUNNER_USER:$RUNNER_USER" "$RUNNER_DIR"
rm -f /tmp/actions-runner.tar.gz

# agent-browser@0.41.2 has a native Linux ARM64 CLI but its bundled Chrome
# installer rejects Linux aarch64. Install Chrome for Testing's published ARM64
# build directly and pass its exact executable path to the CLI.
CHROME_DEPS=(libnss3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
  libpango-1.0-0 libcairo2 libdrm2 libxshmfence1 fonts-liberation fonts-noto-color-emoji)
if [[ "$VERSION_ID" == "24.04" ]]; then
  CHROME_DEPS+=(libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libasound2t64 libatspi2.0-0t64 libgtk-3-0t64)
else
  CHROME_DEPS+=(libatk1.0-0 libatk-bridge2.0-0 libcups2 libasound2 libatspi2.0-0 libgtk-3-0)
fi
apt-get install -y "${CHROME_DEPS[@]}"
CFT_JSON="$(curl -fsSL https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json)"
CFT_VERSION="$(printf '%s' "$CFT_JSON" | jq -r '.channels.Stable.version')"
CFT_URL="$(printf '%s' "$CFT_JSON" | jq -r '.channels.Stable.downloads.chrome[] | select(.platform == "linux-arm64") | .url')"
if [[ -z "$CFT_VERSION" || "$CFT_VERSION" == "null" || -z "$CFT_URL" || "$CFT_URL" == "null" ]]; then
  echo "Chrome for Testing did not publish a Linux ARM64 stable build." >&2
  exit 2
fi
CHROME_DIR="/opt/chrome-for-testing/$CFT_VERSION"
install -d -m 0755 "$CHROME_DIR"
curl -fsSL "$CFT_URL" -o /tmp/chrome-linux-arm64.zip
unzip -q /tmp/chrome-linux-arm64.zip -d "$CHROME_DIR"
rm -f /tmp/chrome-linux-arm64.zip
CHROME_BIN="$CHROME_DIR/chrome-linux-arm64/chrome"
if [[ ! -x "$CHROME_BIN" ]]; then
  echo "Chrome ARM64 executable was not found at $CHROME_BIN" >&2
  exit 2
fi
chmod 0755 "$CHROME_BIN"

# The browser defaults to deny-all domains and deny writes. A workflow must set
# its own allowlist and approval context explicitly for each authorized task.
cat > "$ENV_DIR/browser.env" <<EOF
BLIND_SNIPER_BROWSER_STATE_DIR=$STATE_DIR
BLIND_SNIPER_BROWSER_IDLE_TIMEOUT=0
BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS=
BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS=
BLIND_SNIPER_BROWSER_WRITE_APPROVED=0
AGENT_BROWSER_BIN=$(command -v agent-browser)
AGENT_BROWSER_EXECUTABLE_PATH=$CHROME_BIN
EOF
chmod 0640 "$ENV_DIR/browser.env"
chown root:"$RUNNER_USER" "$ENV_DIR/browser.env"

# Configure the runner without writing the short-lived registration token into a file.
cd "$RUNNER_DIR"
runuser -u "$RUNNER_USER" -- ./config.sh \
  --url "$REPO_URL" \
  --token "$RUNNER_TOKEN" \
  --name "blind-sniper-oracle-$(hostname -s)" \
  --labels "self-hosted,linux,ARM64,blind-sniper-browser" \
  --work "_work" --unattended --replace
unset RUNNER_TOKEN
./svc.sh install "$RUNNER_USER"

SERVICE_UNIT="$(systemctl list-unit-files --type=service --no-legend | awk '$1 ~ /^actions\.runner\./ {print $1; exit}')"
if [[ -z "$SERVICE_UNIT" ]]; then
  echo "Runner service unit was not found after installation." >&2
  exit 2
fi
install -d "/etc/systemd/system/$SERVICE_UNIT.d"
cat > "/etc/systemd/system/$SERVICE_UNIT.d/blind-sniper.conf" <<EOF
[Service]
EnvironmentFile=$ENV_DIR/browser.env
EOF
systemctl daemon-reload
./svc.sh start

echo
echo "Runner installed: $SERVICE_UNIT"
echo "Persistent browser state: $STATE_DIR"
echo "Browser idle timeout: disabled (0)"
echo "Security defaults: empty domain allowlist and write approval disabled."
echo "No paid resources were provisioned by this script. Confirm OCI resources remain inside Always Free quotas."
