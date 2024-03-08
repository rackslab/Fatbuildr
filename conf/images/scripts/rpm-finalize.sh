#!/bin/sh

# This script is used to install Fatbuildr mock plugins and Fatbuildr mock
# environments setup script in RPM image as a mkosi FinalizeScript. This is
# preferred over mkosi ExtraTree as mock plugins path contains the Python
# version which could change over time. The script code can be made more generic
# and not prone to failure when Python version bumps.

if [ $1 != "final" ]; then
    echo "Nothing to do except in final image, exiting."
    exit 0
fi

if [ -z "${BUILDROOT}" ]; then
    echo "BUILDROOT environment variable is not set, exiting."
    exit 0
fi

# Install Mock plugins

echo "Installing fatbuildr mock plugins"
cp -v /usr/share/fatbuildr/images/rpm/mock/*.py \
    $BUILDROOT/usr/lib/python*/site-packages/mockbuild/plugins

# Install Mock environment setup script. Setup consolehelper similarly to mock
# so users in mock groups can execute the utility with root permissions.

echo "Installing fatbuildr build environment setup script"
cp -v /usr/share/fatbuildr/images/rpm/fatbuildr-setup-mockenv \
    $BUILDROOT/usr/libexec
chmod 755 $BUILDROOT/usr/libexec/fatbuildr-setup-mockenv
ln -s consolehelper $BUILDROOT/usr/bin/fatbuildr-setup-mockenv

cat >$BUILDROOT/etc/security/console.apps/fatbuildr-setup-mockenv <<EOF
USER=root
PROGRAM=/usr/libexec/fatbuildr-setup-mockenv
SESSION=false
FALLBACK=false
BANNER=You are not in the 'mock' group.
EOF

cp $BUILDROOT/etc/pam.d/mock $BUILDROOT/etc/pam.d/fatbuildr-setup-mockenv
