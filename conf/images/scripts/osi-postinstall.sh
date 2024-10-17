#!/bin/sh

# Add newuidmap/newgidmap ranges for Fatbuildr system user
echo "fatbuildr:100000:100100" > ${BUILDROOT}/etc/subuid
echo "fatbuildr:100000:100100" > ${BUILDROOT}/etc/subgid
