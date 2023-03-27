# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- web: add JWT token based authentication with RBAC policy for managing access
  permissions to the REST API and the HTML web endpoints (#21). Fatbuildr
  provides a default policy that can be overriden by site administrators.
- conf:
  - Add `[tokens]` section with settings to control generation and
    validation of JWT tokens.
  - Add `policy` and `vendor_policy` settings in `[web]` section to define path
    to RBAC policy definition file loaded by Fatbuildrweb.
- polkit: Add _org.rackslab.Fatbuildr.manage-token_ action
- cli:
  - Add `shell` and `env-shell` operations to `fatbuildrctl images` command to
    open an interactive shell in a container running the image dedicated to a
    given format or in a build environment associated to a distribution (#18).
  - Add `-d, --distribution` option to `fatbuildrctl images` command to filter
    the container images or the build environments targeted by the operation.
  - Add `-a, --architecture` option to `fatbuildrctl images` command to limit
    the build environments targeted by the operation to a specific hardware
    architecture.
  - Add short option `-f` as an alternative to `--format` long option of
    `fatbuildrctl images` command.
  - Add `fatbuildrctl tokens` command to list, generate and save JWT tokens for
    HTTP REST API authentication in user's tokens directory.
  - Add support for JWT token based authentication to Fatbuildrweb REST API.
- prefs: add optional `tokens` parameter in the `prefs` section for specifying
  the path of user's tokens directory.
- pkgs: add dependency on PyJWT python external library for managing JWT tokens.
- docs:
  - Document `tokens` command in `fatbuildrctl` manpage.
  - Document `tokens` parameter in user's preferences file in `fatbuildrctl`
    manpage.
  - Add section about API tokens in `fatbuildrctl` manpage.
  - Add section about authentication in REST API reference page.
  - Mention permission action required by all Fatbuildrweb REST API and HTML
    endpoints in references pages.
  - Document error object returned by REST API for denied permission.
  - Add section about policy configuration in Fatbuildrweb administration page.
  - Document system configuration new `[tokens]` section and new parameters in
    `[web]` section.
  - Mention RBAC policy and JWT authentication in advanced features description.

### Fixed
- cli:
  - Avoid hazardous handling of unsupported errors, as a basis for better
    error management.
  - Handle unknown distribution error in server pipeline (#71)
  - Handle connection error to HTTP URI with readable error message (#10)
  - Print clear error if YAML artifact definition is not found
- daemon: avoid global hazardous catch of all RuntimeErrors and restrict
  handling to supported FatbuildrRuntimeError, as a basis for better error
  management.
- Remove useless imports

### Changed
- cli: transform `images` command options `--create`, `--update`,
  `--create-envs` and `--update-envs` into an operation positional argument with
  the corresponding possible values `create`, `update`, `env-create`,
  `env-update`.
- artifacts: rename YAML artifact definition file from `meta.yml` to
  `artifact.yml`. The old name is still supported but the user is warned with a
  deprecation notice (#73).
- docs: convert APT sources file in quickstart guide from one-line format to
  Deb822-style format (#72)
- Rename `fatbuildr.web` module to `fatbuildr.procotols.http.server` for more
  proximity with `fatbuildr.procotols.http.client` code.

## [1.1.0] - 2023-03-13

### Added

- docs:
  - Add large Fatbuildr logos intended for docs.rackslab.io landing page
  - Add Release notes page based on `CHANGELOG.md`
  - Use tabs for distributions in quickstart guide
  - Mention support of Fedora 37 in quickstart guide (#68)
- conf: add `env_as_root` boolean parameter in `format:{deb,rpm}` section to
  control if commands to create and update build environments are executed as
  root super-user or the user running `fatbuildrd` daemon.
- pkgs: add `CHANGELOG.md` in {deb,rpm} packages
- templates: add `gittag` filter which is notably useful to transform version
  number into valid Git tag in tarball URL.
- lib: make PatchQueue subshell optional
- utils: add import-srcrpm utility to import an existing source RPM package and
  convert it into an artifact defined ready to be consumed by Fatbuildr.

### Fixed
- pkgs: remove useless symbolic link in prescript
- cli:
  - Avoid catching unwanted `AttributeError` exceptions while checking for action
    argument on Python < 3.7.
  - Remove temporary directory after the patch queue is exported instead of
    relying on cleanup registry.
- web:
  - Add missing return to fix the index redirect view (from `/` to
    `/registry`) when Fatbuildrweb is executed in mono-instance mode.
  - Fix support of Flask >= 2.0 (#69)

### Changed
- pkgs:
  - Bump the packaged version of mkosi from 13 to 14
  - Update Fatbuildr packages to depend on mkosi >= 14
- conf:
  - Rename mkosi `--skeleton` option to `--skeleton-tree` to follow mkosi 14
    change.
  - Bump Fedora release from 35 to 37 in rpm and osi container images
- docs:
  - set more generic names for packages repositories in install guide
  - docs: `doc` folder in sources renamed to `docs`

## [1.0.0] - 2022-09-05

[unreleased]: https://github.com/rackslab/fatbuildr/compare/v1.0.0...HEAD
[1.1.0]: https://github.com/rackslab/fatbuildr/releases/tag/v1.1.0
[1.0.0]: https://github.com/rackslab/fatbuildr/releases/tag/v1.0.0
