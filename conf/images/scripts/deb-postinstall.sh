#!/bin/sh

# The systemd package installed in Debian sid OSI image runs systemd-sysusers in
# its deb postinst scripts with its own sysusers.d/*.conf files in arguments.
# This makes systemd-sysusers ignoring the sysusers.d/fatbuildr.conf file
# installed by mkosi skeleton with its explicit UID/GID (to match the host) and
# it could potentially create systemd users and groups with conflicting UID/GID.
# The solution in this postinstall script is to remove possible conflicting user
# and group with the required UID/GID and rerun systemd-sysusers without
# arguments to create all the missing stuff.

EXISTING_USER=$(getent passwd ${FATBUILDR_UID}|cut -d: -f1)
if [ -n "${EXISTING_USER}" ]; then
    echo "Deleting conflicting system user ${EXISTING_USER}"
    userdel $EXISTING_USER
fi

EXISTING_GROUP=$(getent group ${FATBUILDR_GID}|cut -d: -f1)
if [ -n "${EXISTING_GROUP}" ]; then
    echo "Deleting conflicting system group ${EXISTING_GROUP}"
    groupdel $EXISTING_GROUP
fi

systemd-sysusers
