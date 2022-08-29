#!/bin/sh

echo "Adding Fatbuildr user ${FATBUILDR_USER} to mock group"
usermod --append --groups mock ${FATBUILDR_USER}
