#!/bin/sh

# As a work-around for bug https://github.com/systemd/mkosi/issues/644, the
# fedora-release package is re-installed specifying the releasever explicitely
# to make it present in rpm DB and make subsequent dnf executions able to
# detect the release version automatically.
dnf install -y --releasever 35 fedora-release

echo "Adding Fatbuildr user ${FATBUILDR_USER} to mock group"
usermod --append --groups mock ${FATBUILDR_USER}
