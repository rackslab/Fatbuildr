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

import shutil

import createrepo_c as cr

from . import (
    Registry,
    ArtifactVersion,
    RegistryArtifact,
    ChangelogEntry,
    ArtifactMember,
)
from ...log import logr
from ...utils import host_architecture
from ...exec import runcmd
from ...errors import FatbuildrRegistryError

logger = logr(__name__)


class RegistryRpm(Registry):
    """Registry for Rpm format (aka. yum/dnf repository)."""

    def __init__(self, conf, instance):
        super().__init__(conf, instance, 'rpm')

    @property
    def distributions(self):
        return [item.name for item in self.path.iterdir()]

    def derivatives(self, distribution):
        self._check_distribution(distribution)
        return [item.name for item in self.dist_path(distribution).iterdir()]

    def dist_path(self, distribution):
        return self.path.joinpath(distribution)

    def repo_path(self, distribution, derivative, architecture):
        """Returns the path to the repository for the given distribution,
        derivative and normalized architecture."""
        # If the given architecture is noarch, arbitrarily return the path of
        # the host architecture repository.
        if architecture == 'noarch':
            _arch = host_architecture()
        else:
            _arch = architecture
        return self.dist_path(distribution).joinpath(
            derivative, self.archmap.nativedir(_arch)
        )

    def pkg_dir(self, distribution, derivative, architecture):
        return self.repo_path(distribution, derivative, architecture).joinpath(
            'Packages'
        )

    def available_arch_dirs(self, distribution, derivative):
        """Returns the list of Path of existing architectures repositories for
        the given distribution and derivative."""
        return [
            path
            for path in self.dist_path(distribution)
            .joinpath(derivative)
            .iterdir()
        ]

    def _mk_missing_dirs(self, path):
        """Create directory at path if it does not exists, with all its
        parents."""
        if not path.exists():
            logger.info("Creating missing directory %s", path)
            path.mkdir(parents=True)

    def _publish_rpm_arch(self, build, rpm, arch):
        pkg_dir = self.pkg_dir(build.distribution, build.derivative, arch)
        self._mk_missing_dirs(pkg_dir)
        logger.debug("Copying RPM %s to %s", rpm, pkg_dir)
        shutil.copy(rpm, pkg_dir)

    def _publish_rpm(self, build, rpm):
        logger.info("Publishing RPM %s", rpm)
        pkg_arch = rpm.suffixes[-2].lstrip('.')
        if self.archmap.normalized(pkg_arch) == 'noarch':
            # Architecture independent packages must be deployed and duplicated
            # in all supported architectures repositories.
            archs = self.instance.pipelines.architectures
        else:
            archs = [self.archmap.normalized(pkg_arch)]

        logger.debug("Selected repositories architectures: %s", ' '.join(archs))
        for arch in archs:
            self._publish_rpm_arch(build, rpm, arch)
        return archs

    def _update_repo_arch(self, build, arch):
        repo_path = self.repo_path(build.distribution, build.derivative, arch)
        logger.debug("Updating metadata of RPM repository %s", repo_path)
        cmd = ['createrepo_c', '--update', repo_path]
        build.runcmd(cmd)

    def _update_repos(self, build, archs):
        logger.info(
            "Updating metadata of RPM repositories for architectures %s",
            ', '.join(archs),
        )
        for arch in archs:
            self._update_repo_arch(build, arch)

    def _remove_deprecated_rpms(self, build):
        # Search for older versions of source and binary packages having the
        # same source package name in all architectures repositories and remove
        # them.
        for arch in self.instance.pipelines.architectures + ['src']:
            for path in self._packages_paths(
                build.distribution, build.derivative, arch, build.artifact
            ):
                logger.info("Removing replaced RPM %s", path)
                if not path.exists():
                    logger.warning(
                        "Replaced RPM file %s not found, unable to delete",
                        path,
                    )
                    continue
                path.unlink()

    def publish(self, build):
        """Publish RPM (including SRPM) in yum/dnf repository."""

        logger.info(
            "Publishing RPM packages for %s in distribution %s",
            build.artifact,
            build.distribution,
        )
        # first remove deprecated RPM packages
        self._remove_deprecated_rpms(build)

        # Then publish new version of packages and collect list of involved
        # architectures.
        archs = []
        for rpm in build.place.glob('*.rpm'):
            archs.extend(self._publish_rpm(build, rpm))

        # Update repositories of involved architectures, without duplicates.
        self._update_repos(build, list(set(archs)))

    def _packages_paths(self, distribution, derivative, architecture, artifact):
        """Returns the list of paths of all binary RPM generated by the given
        source artifact and the path to the corresponding source RPM."""
        paths = []
        repo_path = self.repo_path(distribution, derivative, architecture)
        md = cr.Metadata()
        try:
            md.locate_and_load_xml(str(repo_path))
        except OSError:
            logger.warning(
                "Unable to load RPM repository metadata in directory %s",
                repo_path,
            )
            # If packages Metadata is not found, createrepo_c raises an OSError.
            # In this case, the repository is necessarily empty.
            return []
        for key in md.keys():
            pkg = md.get(key)
            if (pkg.arch == 'src' and pkg.name == artifact) or (
                pkg.arch != 'src'
                and pkg.rpm_sourcerpm.rsplit('-', 2)[0] == artifact
            ):
                paths.append(repo_path.joinpath(pkg.location_href))
        return paths

    def artifacts(self, distribution, derivative):
        """Returns the list of artifacts in rpm repository."""
        self._check_derivative(distribution, derivative)
        artifacts = []
        for arch_dir in self.available_arch_dirs(distribution, derivative):
            md = cr.Metadata()
            try:
                md.locate_and_load_xml(str(arch_dir))
            except OSError:
                logger.warning(
                    "Unable to load RPM repository metadata in directory %s",
                    arch_dir,
                )
                # If packages Metadata is not found, createrepo_c raises an
                # OSError. In this case, the repository is necessarily empty.
                return []
            for key in md.keys():
                pkg = md.get(key)
                artifact = RegistryArtifact(
                    pkg.name, pkg.arch, pkg.version + '-' + pkg.release
                )
                # Architecture independant packages can be duplicated in
                # multiple architectures repositories. We check the
                # RegistryArtifact is not already present in list to avoid
                # duplicated entries in resulting list.
                if artifact not in artifacts:
                    artifacts.append(artifact)
        return artifacts

    def artifact_bins(self, distribution, derivative, src_artifact):
        """Returns the list of binary RPM generated by the given source RPM."""
        artifacts = []
        for arch_dir in self.available_arch_dirs(distribution, derivative):
            md = cr.Metadata()
            md.locate_and_load_xml(str(arch_dir))
            for key in md.keys():
                pkg = md.get(key)
                if pkg.arch == 'src':  # skip non-binary package
                    continue
                # The createrepo_c library gives access to full the source RPM
                # filename, including its version and its extension. We must
                # extract the source package name out of this filename.
                source = pkg.rpm_sourcerpm.rsplit('-', 2)[0]
                if source != src_artifact:
                    continue
                artifact = RegistryArtifact(
                    pkg.name, pkg.arch, pkg.version + '-' + pkg.release
                )
                # Architecture independant packages can be duplicated in
                # multiple architectures repositories. We check the
                # RegistryArtifact is not already present in list to avoid
                # duplicated entries in resulting list.
                if artifact not in artifacts:
                    artifacts.append(artifact)
        return artifacts

    def artifact_src(self, distribution, derivative, bin_artifact):
        for arch_dir in self.available_arch_dirs(distribution, derivative):
            md = cr.Metadata()
            md.locate_and_load_xml(str(arch_dir))
            for key in md.keys():
                pkg = md.get(key)
                if pkg.name != bin_artifact:
                    continue
                if pkg.arch == 'src':  # skip non-binary package
                    continue
                # The createrepo_c library gives access to the full source RPM
                # filename, including its version and its extension. We must
                # extract the source package name out of this filename.
                srcrpm_components = pkg.rpm_sourcerpm.rsplit('-', 2)
                src_name = srcrpm_components[0]
                # For source version, extract the version and the release with
                # .src.rpm suffix removed.
                src_version = (
                    srcrpm_components[1] + '-' + srcrpm_components[2][:-8]
                )
                return RegistryArtifact(src_name, 'src', src_version)

    def source_version(self, distribution, derivative, artifact):
        """Returns the version of the given source package name, or None if not
        found."""
        md = cr.Metadata()
        try:
            md.locate_and_load_xml(
                str(self.repo_path(distribution, derivative, 'src'))
            )
        except OSError:
            # If packages Metadata is not found, createrepo_c raises an OSError.
            # In this case, the repository is necessarily empty.
            return None
        for key in md.keys():
            pkg = md.get(key)
            if pkg.name != artifact:
                continue
            if pkg.arch != 'src':  # skip binary package
                continue
            return ArtifactVersion(f"{pkg.version}-{pkg.release}")
        return None

    def changelog(self, distribution, derivative, architecture, artifact):
        """Returns the changelog of a RPM source package."""
        self._check_derivative(distribution, derivative)
        repo_path = self.repo_path(distribution, derivative, architecture)
        if not repo_path.exists():
            raise FatbuildrRegistryError(
                "Unable to find repository path for architecture "
                f"{architecture} in distribution {distribution} and "
                f"derivative {derivative}"
            )
        md = cr.Metadata()

        md.locate_and_load_xml(str(repo_path))
        for key in md.keys():
            pkg = md.get(key)
            if pkg.name != artifact:
                continue
            if pkg.arch != architecture:
                continue
            return RpmChangelog(pkg.changelogs).entries()
        raise FatbuildrRegistryError(
            f"Unable to find RPM package {artifact} with architecture "
            f"{architecture} in distribution {distribution} and derivative "
            f"{derivative}"
        )

    @staticmethod
    def _artifact_content_from_rpm_query(package_path):
        cmd = [
            'rpm',
            '--query',
            '--queryformat',
            "[%{FILENAMES} %{FILEMODES:perms} %{FILESIZES}\n]",
            '--package',
            package_path,
        ]
        proc = runcmd(cmd)
        result = []
        for line in proc.stdout.decode().splitlines():
            (path, mode, size) = line.split(' ')
            result.append(
                ArtifactMember(
                    path, 'f' if mode.startswith('-') else mode[0], int(size)
                )
            )
        return result

    def artifact_content(
        self, distribution, derivative, architecture, artifact
    ):
        self._check_derivative(distribution, derivative)
        repo_path = self.repo_path(distribution, derivative, architecture)
        if not repo_path.exists():
            raise FatbuildrRegistryError(
                "Unable to find repository path for architecture "
                f"{architecture} in distribution {distribution} and "
                f"derivative {derivative}"
            )
        md = cr.Metadata()

        md.locate_and_load_xml(str(repo_path))
        for key in md.keys():
            pkg = md.get(key)
            if pkg.name != artifact:
                continue
            if pkg.arch == 'src':  # skip non-binary package
                continue
            return self._artifact_content_from_rpm_query(
                repo_path.joinpath(pkg.location_href)
            )
        raise FatbuildrRegistryError(
            f"Unable to find RPM package {artifact} with architecture "
            f"{architecture} in distribution {distribution} and derivative "
            f"{derivative}"
        )

    def delete_artifact(self, distribution, derivative, artifact):

        if artifact.architecture == 'noarch':
            # If the architecture is noarch (ie. binary architecture
            # independant package), the package might be duplicated in all
            # architectures repositories. We must explicitely loop over all
            # architectures to fully remove the binary package.
            archs = [
                self.archmap.native(arch)
                for arch in self.instance.pipelines.architectures
            ]
        else:
            archs = [self.archmap.native(artifact.architecture)]

        for arch in archs:
            md = cr.Metadata()
            repo_path = self.repo_path(distribution, derivative, arch)
            md.locate_and_load_xml(str(repo_path))
            for key in md.keys():
                pkg = md.get(key)
                if (
                    pkg.name == artifact.name
                    and pkg.arch == artifact.architecture
                ):
                    pkg_path = repo_path.joinpath(pkg.location_href)
                    logger.info("Deleting RPM package %s", pkg_path)
                    if not pkg_path.exists():
                        logger.warning(
                            "RPM file %s not found, unable to delete", pkg_path
                        )
                    else:
                        pkg_path.unlink()

            logger.info(
                "Updating metadata of RPM repository %s",
                repo_path,
            )
            cmd = [
                'createrepo_c',
                '--update',
                repo_path,
            ]
            runcmd(cmd)


class RpmChangelog:
    def __init__(self, entries):
        self._entries = entries

    def entries(self):
        result = []
        # The createrepo_c library builds the entries list in ascending date
        # order. We prefer to list the entries to other way, so we reverse.
        for entry in reversed(self._entries):

            (author, version) = entry[cr.CHANGELOG_ENTRY_AUTHOR].rsplit(' ', 1)
            changes = [
                RpmChangelog._sanitize_entry(entry)
                for entry in entry[cr.CHANGELOG_ENTRY_CHANGELOG].split('\n')
            ]
            result.append(
                ChangelogEntry(
                    version, author, entry[cr.CHANGELOG_ENTRY_DATE], changes
                )
            )
        return result

    @staticmethod
    def _sanitize_entry(entry):
        # remove leading dash if present
        if entry.startswith('-'):
            entry = entry[1:]
        return entry.strip()
