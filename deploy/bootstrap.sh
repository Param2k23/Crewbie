#!/usr/bin/env bash
# One-time setup of the EC2 instance (Ubuntu 24.04). Safe to run again.
#   sudo bash /opt/crewbie/deploy/bootstrap.sh
set -euo pipefail

if [ "$(id -u)" != "0" ]; then
    echo "Run with sudo: sudo bash deploy/bootstrap.sh" >&2
    exit 1
fi
APP_USER="${SUDO_USER:-ubuntu}"
export DEBIAN_FRONTEND=noninteractive

echo "==> Updating packages"
apt-get update
apt-get upgrade -y
apt-get install -y ca-certificates curl git sqlite3 unattended-upgrades

echo "==> Swap (1 GB RAM is tight while building the image)"
if [ ! -f /swapfile ]; then
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
fi
swapon --show=NAME | grep -qx /swapfile || swapon /swapfile
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab

echo "==> Docker Engine and Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
# Containers with `restart: unless-stopped` then come back after every instance start.
systemctl enable --now docker
usermod -aG docker "${APP_USER}"

echo "==> App directory"
mkdir -p /opt/crewbie
chown "${APP_USER}:${APP_USER}" /opt/crewbie

echo "==> Timezone (logs only; the application stores UTC)"
timedatectl set-timezone America/Phoenix

echo "==> Automatic security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo
echo "Done. Log out and back in so the docker group applies to ${APP_USER}."
