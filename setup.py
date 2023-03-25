#!/usr/bin/env python3
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

from setuptools import setup, find_packages

# get __version__
exec(open('fatbuildr/version.py').read())

setup(name='Fatbuildr',
      version=__version__,
      packages=find_packages(),
      author='Rémi Palancher',
      author_email='remi@rackslab.io',
      license='GPLv3+',
      url='https://github.com/rackslab/fatbuildr',
      platforms=['GNU/Linux'],
      install_requires=['Jinja2>=2.11.0',
                        'gpg',
                        'requests',
                        'PyJWT',
                        'PyYAML',
                        'createrepo-c',
                        'Flask',
                        'pygit2',
                        'python-debian',
                        'dasbus>=1.6'],
      entry_points = {
          'console_scripts': [
              'fatbuildrd=fatbuildr.cli.fatbuildrd:Fatbuildrd.run',
              'fatbuildrctl=fatbuildr.cli.fatbuildrctl:Fatbuildrctl.run',
              'fatbuildrweb=fatbuildr.cli.fatbuildrweb:FatbuildrWeb.run'
          ],
      })
