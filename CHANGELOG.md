# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Add `man` command in OSI format container image.
- Additionally to `*.tar` images, publish OSI registry all other images formats 
  supported by `mkosi` (#112).
- Give the possibility to run OSI builds directly on host instead of container
  to support images formats for which `mkosi` utility require access to loop
  devices (#111).
- Support multiples OSI images in the checksum file published in the same
  registry derivative directory (#114).
- Possiblity to define patches templates with variables to replace (#128).
- cli: Possibility to list artifacts in registries in remote instance with REST
  API (#141)
- web: Report fatbuildr version in footer of fatbuildrweb HTML pages (#108).
- conf: Add `containerized` parameter in `[format:osi]` section.
- pkgs: Add patch to define upstream version at build time.
- polkit: Add _org.rackslab.Fatbuildr.edit-registry-as_ action.
- docs:
  - Mention `containerized` parameter in `[format:osi]` section of system
    configuration.
  - Document patches DEP-3 metadata support with Fatbuildr specific fields and
    their management with fatbuildrctl patches subcommand.
  - Mention patches deb822 `Template` field and the patches templating feature.
  - Mention possibility of missing JWT signing key for REST API HTTP/404 reponse
    code.
  - Document impact of HTTP reverse proxies buffering on tasks output streams
    with mention of possible configuration settings.

### Fixed
- Fix crash on client side when loading artifact definition for OSI builds
  (#100).
- Fix crash due to concatation with incompatible types when defining the full
  release for OSI build on server side (#101).
- Add `apt` command in container for OSI image to meet Debian and Ubuntu based
  images build requirements (#102).
- Fix `systemd-nspawn` execution error through `mkosi` in OSI format container
  caused by unavailability of DBus system session (#103).
- Fix GPG keys unsupported filetype error when running `apt-get update` on build
  of Debian OSI images due to missing `cmp` command (#104).
- Search mkosi output image and checksum file in distro~release subdirectory in
  OSI builds (#105).
- Fix permission error on OSI artifacts produced by mkosi by faking sudo
  environment (#106).
- Fix AttributeError in fatbuildrd when publishing OSI artifacts (#107).
- Make RegistryOsi ensure instance registry directory exists (#109).
- Add missing chattr command in OSI container image (#110).
- Fix wrongly filtered out files containing debian or .git words in their path
  when building local archive on build submission (#113).
- Fix unusable version.dist variable in packaging code templates (#116).
- Fix crash on build on unsupported derivative in instance pipelines (#117).
- Fix crash on retrieving derivative version in artifact definition (#118).
- Fix crash when main archive source is not defined on build of Deb or RPM
  package (#119).
- Fix crash on missing checksum for a specific version in artifact definition
  file (#125).
- Fix crash in fatbuildrweb 404 error handler when HTTP request view arguments
  are not defined due to error during view matching (#126).
- Fix retrieval of instances list in DBus and fatbuildrweb when default instance
  is not defined (#127).
- Fix crash in fatbuildrctl when user preferences file is missing (#130).
- Fix crash in fatbuildrd when running containers with empty `init_opts` in site
  configuration file (#131).
- Return HTTP/404 with appropriate error message instead of HTTP/500 (internal
  error) when trying to access exported armored public key on nonexistent
  keyring with fatbuildrweb (#133).
- Report error properly with fatbuildrctl when remote HTTP instance replies with
  internal error and HTTP/500 (#136).
- Report meaningful error message instead of generic HTTP/500 internal error
  when authenticating with JWT token on unexisting remote HTTP instance (#137).
- Fix crash with when watching streamed tasks output with HTTP REST API (#138).
- Avoid buffering with HTTP response headers on reverse proxies (#139).

## [2.0.0] - 2023-05-05

### Added
- web: add JWT token based authentication with RBAC policy for managing access
  permissions to the REST API and the HTML web endpoints (#21). Fatbuildr
  provides a default policy that can be overriden by site administrators.
- Associate tasks to originating users (#79)
- Automatic static analysis of RPM and Deb packages based on rpmlint and lintian
  after successful build (#16)
- Add support of interactive build for RPM packages format (#61)
- Add support of multiple sources for packages artifacts (#66)
- Report Deb and RPM packages content after successful builds, with additional
  pbuilder hook and mock plugin respectively (#74)
- Add possibility to purge tasks history and their workspaces directories with
  multiple configurable policies (#34)
- Add support of plain files as additional sources in RPM packages (#86)
- conf:
  - Add `[tokens]` section with settings to control generation and
    validation of JWT tokens.
  - Add `policy` and `vendor_policy` settings in `[web]` section to define path
    to RBAC policy definition file loaded by Fatbuildrweb.
  - Add `[tasks]` section with parameters to specify tasks workspaces location
    and tasks history purge policy.
- polkit:
  - Add _org.rackslab.Fatbuildr.manage-token_ action.
  - Add _org.rackslab.Fatbuildr.build-as_ action.
  - Add _org.rackslab.Fatbuildr.purge-history_ action.
- dbus:
  - Add `BuildAs` method to `org.rackslab.Fatbuildr.Instance` object to submit
    build task with another user identity.
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
  - Add support of HTTP/404 REST API response codes.
- prefs: add optional `tokens` parameter in the `prefs` section for specifying
  the path of user's tokens directory.
- utils:
  - Add support of multiple sources archives in `import-srcrpm`.
  - Add support of plain files as RPM packages sources in `import-srcrpm`.
- pkgs: add dependency on PyJWT python external library for managing JWT tokens.
- docs:
  - Document `tokens` command in `fatbuildrctl` manpage.
  - Document `tokens` parameter in user's preferences file in `fatbuildrctl`
    manpage.
  - Document new `history purge` subcommand in in `fatbuildrctl` manpage
  - Add section about API tokens in `fatbuildrctl` manpage.
  - Add section about Local sources and `--sources` option value format in
    `fatbuildrctl` manpage.
  - Add section about authentication in REST API reference page.
  - Mention new polkit actions _org.rackslab.Fatbuildr.manage-token_,
    _org.rackslab.Fatbuildr.purge-history_ and _org.rackslab.Fatbuildr.build-as_
    with a special note for _*-as_ actions.
  - Mention permission action required by all Fatbuildrweb REST API and HTML
    endpoints in references pages.
  - Document error object returned by REST API for denied permission.
  - Add section about policy configuration in Fatbuildrweb administration page.
  - Document system configuration new `[tokens]` section and new parameters in
    `[web]` section.
  - Document new `purge` parameter in `[tasks]` section.
  - Mention multiple sources support, static analysis, packages content listing,
    RBAC policy and JWT authentication in advanced features description.
  - Add page about packages source tree with all principles followed for various
    types of sources illustrated by new diagrams.
  - Mention HTTP/404 reponse codes in REST API when instance or task is unknown
    by fatbuildrd and when format, distribution, derivative, architecture or
    artifact is not found in registries.
  - Add page about tasks history purge capabilities with the various policies,
    the expected format of the limit value in configuration parameter and a
    quick howto setup regular automatic purge with a cronjob.
  - Add example cronjob for automatic regular tasks history purge.
  - Mention possibility to have additional plain files in the `rpm` subdirectory
    of artifacts definitions repository.

### Fixed
- Static analysis errors reported by ruff tool with a simple initial
  configuration (#75).
- Properly remove deprecated source RPM packages from repository after a
  successful build (#58).
- Compiler `-Wunused-result` warnings with binary wrappers (#70).
- cli:
  - Avoid hazardous handling of unsupported errors, as a basis for better
    error management.
  - Handle unknown distribution error in server pipeline (#71)
  - Handle connection error to HTTP URI with readable error message (#10)
  - Print clear error if YAML artifact definition is not found
- daemon: avoid global hazardous catch of all RuntimeErrors and restrict
  handling to supported FatbuildrRuntimeError, as a basis for better error
  management.
- Avoid removal of tilde from version extracted in source tarball filename
  when submitted during build through HTTP REST API (#81).
- Remove useless imports
- images:
  - Fix fatbuildr user and group with host UID/GID in deb format container image
    due to possible conflicts with other installed Debian sid packages (#83)
  - Add missing shebang in derivatives pbuilder hook
- docs: Fix prescript token names in artifact definition reference.

### Changed
- Merge queue and archives directories into a common workspaces directory (#88)
- cli:
  - Transform `images` command options `--create`, `--update`, `--create-envs`
    and `--update-envs` into an operation positional argument with the
    corresponding possible values `create`, `update`, `env-create`,
    `env-update`.
  - Replace `fatbuildrctl {patches,build}` command options `--source-dir` and
    `--source-version` by generic option `--sources`.
  - Replace `fatbuildrctl archives` by `fatbuildrctl history` command to avoid
    confusion with the notion of source archives (#87)
- artifacts:
  - Rename YAML artifact definition file from `meta.yml` to `artifact.yml`. The
    old name is still supported but the user is warned with a deprecation notice
    (#73).
  - Replace `tarball` option by `source` or `sources`, depending on the number
    of archive sources.
  - Modify format of `versions`, `derivatives` and `checksums` keys to support
    optional multiple sources for packages artifacts.
  - The RPM spec file token `{{ source }}` is replaced by `{{ sources }}` to
    declare possibly multiple sources.
- conf:
  - Replaced `queue` and `archives` parameters in `[dirs]` section of system
    configuration by `workspaces` parameter in `[tasks]` section.
  - Bump Fedora release from 37 to 38 in rpm and osi container images (#96).
- dbus: Replace `Archives()` by `History()` method in
  `org.rackslab.Fatbuildr.Instance` object to avoid confusion with the notion of
  source archives.
- web:
  - Build tasks are submitted to fatbuildrd with original requesting user's
    identity when fatbuildrd runs with another user (typically `fatbuildr`
    system user) so the tasks are properly associated to the original user.
  - Return HTTP/404 with clear error message when instance or task is unknown by
    fatbuildrd and when format, distribution, derivative, architecture or
    artifact is not found in registries (#64).
  - Introduce new array of `SourceArchive` objects in the properties of `Task`
    JSON objects for build tasks.
  - Modify optional source archives filename multipart build requests to support
    sending of multiples sources.
- docs:
  - Convert APT sources file in quickstart guide from one-line format to
    Deb822-style format (#72)
  - Modify artifact definition reference documentation with changes introduced
    to support packages artifacts with multiple sources and many examples to
    cover most cases.
  - Modify REST API reference with changes introduced to support packages
    artifacts with multiple sources.
  - Replace options `--source-dir` and `--source-version` by `--sources` in
    `fatbuildrctl` manpage.
  - Modify system configuration reference to mention replacement of `queue` and
    `archives` in `[dirs]` section by common `workspaces` parameter in `[tasks]`
    section.
  - Update example outputs with new common workspaces directory to match new
    default paths.
  - Replace notion of _archives_ by _history_ to designate the list of
    terminated tasks.
  - Update support fedora release in quickstart guide to 37 and 38. Also update
    example instance file to mention fedora 38 instead of fedora 36.
- Rename `fatbuildr.web` module to `fatbuildr.procotols.http.server` for more
  proximity with `fatbuildr.procotols.http.client` code.
- pkgs:
  - Adapt artifact definitions and packaging code for fatbuildr and its
    dependencies to new format defined for multiple sources support.
  - Replace fatbuildr prescript with a supplementary source for bootstrap.
  - Bump dasbus dependency to latest version 1.7 (#67).
- examples: Change hello package artifact definition to new format defined for
  multiple sources support.

### Removed
- pkgs: removed support of Fedora 36
- docs: removed mention of Fedora 36 in quickstart guide

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

[unreleased]: https://github.com/rackslab/fatbuildr/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/rackslab/fatbuildr/releases/tag/v2.0.0
[1.1.0]: https://github.com/rackslab/fatbuildr/releases/tag/v1.1.0
[1.0.0]: https://github.com/rackslab/fatbuildr/releases/tag/v1.0.0
