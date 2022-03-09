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

# This script is the pre-script wrapper, it contains functions to simply common
# tasks in pre-scripts.

function DL() {
    URL=$1
    DEST=$2
    echo "PRE: DL: ${URL} > ${DEST}"
    wget --quiet ${URL} --output-document ${DEST}
}

if [ -z $1 ]; then
    echo "Script path must be given in argument"
fi

. $1
