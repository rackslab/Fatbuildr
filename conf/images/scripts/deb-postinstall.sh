#!/bin/sh

# Debian packages installed in OSI image do not call systemd-sysusers in their
# postinst scripts. Then it is called explicitely here to create missing
# sysusers, and especially fatbuildr system user.
systemd-sysusers
