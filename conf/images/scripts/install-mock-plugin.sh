#!/bin/sh

# This script is used to install Fatbuildr mock plugin in RPM image as a mkosi
# FinalizeScript. This is preferred over mkosi ExtraTree as mock plugins path
# contains the Python version which could change over time. The script code can
# be made more generic and not prone to failure when Python version bumps.

if [ $1 != "final" ]; then
    echo "Nothing to do except in final image, exiting."
    exit 0
fi

if [ -z "${BUILDROOT}" ]; then
    echo "BUILDROOT environment variable is not set, exiting."
    exit 0
fi

echo "Installing fatbuildr mock plugins"
cp -v /usr/lib/fatbuildr/images/rpm/mock/*.py \
    $BUILDROOT/usr/lib/python*/site-packages/mockbuild/plugins
