# Fatbuildr

## Overview

Fatbuildr is an open source solution designed to build software and distribute
them in various formats. It acts as a continuous delivery solution. It takes
software and artifact definitions inputs, then it builds artifacts based on
definitions and publish them in registries.

<img
  src="doc/modules/overview/images/fatbuildr_overview.svg"
  alt="Fatbuildr Overview"
  style="display: inline-block; margin: 0 auto; max-width: 600px">

Typically, Fatbuildr is used to build deb and RPM packages and publish them in
APT and DNF repositories, or build containers images and publish them in
containers registries.

Fatbuildr manages artifacts definitions, build environments, the registries with
their content and the signing keyring in a reproducible and automated manner. It
helps organizations maintaining their software artifacts, including their
dependencies, with high level of consistency and security.

Fatbuildr currently supports the following artifacts formats:

* RPM packages
* Deb packages
* OSI images

The software is fully modular and extensible, more supported formats can be
easily added.

For more details, read the
[full description](https://docs.rackslab.io/fatbuildr/overview/what.html) of
Fatbuildr and discover its
[advanced features](https://docs.rackslab.io/fatbuildr/overview/features.html).

## Quickstart

To install and start using Fatbuildr in a few steps, follow the
[quickstart guide](https://docs.rackslab.io/fatbuildr/install/quickstart.html)!

## Documentation

The [full documentation](https://docs.rackslab.io/fatbuildr/overview/start.html)
of Fatbuildr is available online with internal architectures diagrams, advanced
installation and configuration details and complete users reference guide.

## Authors

Fatbuildr is developed and maintained by [Rackslab](https://rackslab.io). Please
[contact us](https://rackslab.io/en/contact/) for any questions or professionnal
services.

## License

Fatbuildr is distributed under the terms of the GNU General Public License v3.0
or later (GPLv3+).
