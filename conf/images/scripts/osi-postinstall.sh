#!/bin/sh

# Add newuidmap/newgidmap ranges for Fatbuildr system user
echo "fatbuildr:100000:100100" > /etc/subuid
echo "fatbuildr:100000:100100" > /etc/subgid
