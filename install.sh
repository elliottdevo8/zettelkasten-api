#!/usr/bin/env bash
# Install zettelkasten-api systemd user services.
# Run once after cloning; re-run after updating service templates.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

mkdir -p "${SYSTEMD_USER_DIR}"

for template in "${REPO_DIR}"/*.service.template; do
    service_name="$(basename "${template}" .template)"
    sed "s|__REPO_DIR__|${REPO_DIR}|g" "${template}" > "${SYSTEMD_USER_DIR}/${service_name}"
    echo "Installed: ${SYSTEMD_USER_DIR}/${service_name}"
done

systemctl --user daemon-reload
echo ""
echo "Done. Enable and start the server with:"
echo "  systemctl --user enable --now zettelkasten-api.service"
