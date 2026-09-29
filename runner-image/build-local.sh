#!/usr/bin/env bash
# Build the generated-tool runner image WITHOUT Docker Hub (for networks that block it).
# Creates a minimal Ubuntu 24.04 + Python 3 root filesystem from the Ubuntu package mirror
# and imports it as aiea-python-base:local. Run as root inside WSL/Linux:
#   wsl -d Ubuntu -u root -- bash runner-image/build-local.sh
# Needs: docker, debootstrap (apt-get install -y docker.io debootstrap).
set -u
W=/var/tmp/aiea-rootfs
rm -rf "$W" && mkdir -p "$W"
debootstrap --variant=minbase --include=python3 noble "$W" http://archive.ubuntu.com/ubuntu > /var/tmp/debootstrap.log 2>&1
code=$?
echo "debootstrap-exit=$code"
grep -E '^(E|W):' /var/tmp/debootstrap.log | head -5
if [ $code -ne 0 ] || [ ! -x "$W/usr/bin/python3" ]; then
  echo "BUILD FAILED"; tail -5 /var/tmp/debootstrap.log; exit 1
fi
docker rmi -f aiea-python-base:local > /dev/null 2>&1
tar -C "$W" -c . | docker import - aiea-python-base:local > /dev/null
docker images aiea-python-base --format '{{.Repository}}:{{.Tag}} {{.Size}}'
