# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- docs: add large Fatbuildr logos intended for docs.rackslab.io landing page
- conf: add env_as_root boolean parameter in format:{deb,rpm} section to control
  if commands to create and update build environments are executed as root
  super-user or the user running fatbuildrd daemon.

### Fixed
- pkgs: remove useless symbolic link in pre

### Changed
- pkgs:
  - Bump the packaged version of mkosi from 13 to 14
  - Update Fatbuildr packages to depend on mkosi >= 14
- conf: rename mkosi --skeleton option to --skeleton-tree to follow mkosi 14
  change
- docs: set more generic names for packages repositories in install guide

## [1.0.0] - 2022-09-05

[unreleased]: https://github.com/rackslab/fatbuildr/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rackslab/fatbuildr/releases/tag/v1.0.0
