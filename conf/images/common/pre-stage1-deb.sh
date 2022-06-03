#!/bin/bash
#
# Copyright (C) 2021 Rackslab
#
# This file is part of Fatbuildr.
#
# Fatbuildr is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Fatbuildr is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Fatbuildr.  If not, see <https://www.gnu.org/licenses/>.
# our imports

# This script is the Deb stage1 pre-script wrapper. It setups the environment
# required to run the pre-wrapper in cowbuilder environment with the correct
# user.

if [ -z $2 ]; then
    echo "Pre-wrapper script and prescript paths must be given in argument"
fi

# Create fatbuildr user in build environment and run provided pre script with
# this user.
groupadd --gid ${FATBUILDR_GID} ${FATBUILDR_USER}
useradd --system --uid ${FATBUILDR_UID} --gid ${FATBUILDR_GID} ${FATBUILDR_USER}

# install deps in pre-script build environment
DEBIAN_FRONTEND=noninteractive apt-get -y install wget ca-certificates

#cd ${FATBUILDR_SOURCE_DIR}
su ${FATBUILDR_USER} -s /bin/bash -c "/bin/bash $1 $2"
