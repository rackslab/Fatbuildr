#!/bin/bash

FATBUILDR_IMG_DIR="/var/lib/fatbuildr/images"
# The images built with mkosi have a symlink
# /etc/resolv.conf → /run/systemd/resolve/* as they expect systemd-resolved to
# run inside the containers (ie. systemd-nspawn -B).
NSPAWN_OPTS="--resolv-conf=replace-stub"
RPM_DISTS="rocky-8-x86_64"
DEB_DISTS="sid bookworm bullseye"

if [ -d ${FATBUILDR_IMG_DIR} ]; then
    mkdir -p ${FATBUILDR_IMG_DIR}
fi

for OS in deb rpm; do
    mkosi --default=images/build/${OS}.mkosi
done

for DISTRIBUTION in ${RPM_DISTS}; do
    # NOTE: perl is required by slurm spec file to build source RPM
    systemd-nspawn --directory ${FATBUILDR_IMG_DIR}/rpm.img ${NSPAWN_OPTS} \
      mock --init --root=$DISTRIBUTION \
        --config-opts="chroot_additional_packages=perl"
done

for DISTRIBUTION in ${DEB_DISTS}; do
    systemd-nspawn --directory ${FATBUILDR_IMG_DIR}/deb.img ${NSPAWN_OPTS} \
      cowbuilder --create --distribution $DISTRIBUTION \
        --basepath /var/cache/pbuilder/$DISTRIBUTION
done
