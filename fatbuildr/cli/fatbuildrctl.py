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

import argparse
import sys
import os
import time
from pathlib import Path
import tempfile
import tarfile

from . import FatbuildrCliRun
from ..version import __version__
from ..prefs import UserPreferences
from ..log import logr
from ..protocols import ClientFactory
from ..protocols.crawler import register_protocols
from ..protocols.wire import WireSourceArchive
from ..artifact import ArtifactDefs, ArtifactDefsFactory
from ..patches import PatchQueue
from ..git import load_git_repository
from ..tokens import ClientTokensManager
from ..console.client import tty_console_renderer
from ..errors import (
    FatbuildrRuntimeError,
    FatbuildrArtifactError,
    FatbuildrServerError,
    FatbuildrServerPermissionError,
)

logger = logr(__name__)


DEFAULT_URI = 'dbus://system/default'


def progname():
    """Return the name of the program."""
    return Path(sys.argv[0]).name


def prepare_tarball(apath, rundir: bool):
    """Generates tarball container artifact definition. If rundir is True, the
    tarball is generated in fatbuildrd system runtime directory. Otherwise, it
    is generated in default temporary directory."""

    if rundir:
        base = Path('/run/fatbuildr')
    else:
        base = Path(tempfile._get_default_tempdir())

    tarball = base.joinpath(
        f"fatbuildr-artifact-{next(tempfile._get_candidate_names())}.tar.xz"
    )

    if not apath.exists():
        raise RuntimeError(
            f"artifact definition directory {apath} does not exist",
        )

    logger.debug(
        "Creating archive %s with artifact definition directory %s",
        tarball,
        apath,
    )
    tar = tarfile.open(tarball, 'x:xz')
    tar.add(apath, arcname='.', recursive=True)
    tar.close()

    return tarball


def prepare_source_tarball(
    artifact, path, version, rundir: bool, include_git_untracked: bool
):
    """Generates a source tarball for the given artifact, tagged with the given
    main version, using sources in path."""

    if rundir:
        base = Path('/run/fatbuildr')
    else:
        base = Path(tempfile._get_default_tempdir())

    logger.info(
        "Generating artifact %s source tarball version %s using directory %s",
        artifact,
        version,
        path,
    )
    if not path.exists():
        logger.error(
            "Given source directory %s for artifact %s does not exists, "
            "leaving",
            path,
            artifact,
        )
        sys.exit(1)
    subdir = f"{artifact}-{version}"
    tarball = base.joinpath(f"{artifact}-{version}.tar.xz")

    if tarball.exists():
        logger.warning(
            "Tarball %s already exists, it may have been generated for a "
            "previous failed build, trying to remove it in the first place.",
            tarball,
        )
        tarball.unlink()
    logger.debug(
        "Creating artifact %s source tarball %s with directory %s",
        artifact,
        tarball,
        path,
    )

    # If .git directory is present in source path, load existing git repository.
    git_repo = None
    if path.joinpath(".git").exists():
        git_repo = load_git_repository(path)

    def source_tarball_filter(tarinfo):
        """Custom tar add filter to filter out .git directory, .git* files (eg.
        .gitignore), debian subdirectory and files mentioned in .gitignore from
        source tarball."""

        # Extract filename from tarinfo.name without tarball top-level directory
        # by removing part before the first OS separator. If the OS separator is
        # not found in filename, then consider the whole filename.
        try:
            filename = tarinfo.name.split(os.sep, 1)[1]
        except IndexError:
            filename = tarinfo.name
        if (
            filename.startswith('.git')
            or filename == 'debian'
            or filename.startswith('debian/')
        ):
            return None
        # If the source tree is a git repository and the file is ignored in the
        # repository, exclude this file from generated archive.
        if (
            git_repo is not None
            and not include_git_untracked
            and git_repo.path_is_ignored(filename)
        ):
            logger.debug(
                "Excluded file untracked in git repository: %s", tarinfo.name
            )
            return None
        logger.debug("File added in archive: %s", tarinfo.name)
        return tarinfo

    with tarfile.open(tarball, 'x:xz') as tar:
        tar.add(
            path, arcname=subdir, recursive=True, filter=source_tarball_filter
        )
    return tarball


class Fatbuildrctl(FatbuildrCliRun):
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Do something with fatbuildr.'
        )
        parser.add_argument(
            '-v',
            '--version',
            dest='version',
            action='version',
            version='%(prog)s ' + __version__,
        )
        parser.add_argument(
            '--debug',
            dest='debug',
            action='store_true',
            help="Enable debug mode",
        )
        parser.add_argument(
            '--fulldebug',
            action='store_true',
            help="Enable debug mode in external libs",
        )
        parser.add_argument(
            '--preferences',
            help="Path to user preference file (default: %(default)s)",
            type=Path,
            default=UserPreferences.DEFAULT,
        )
        parser.add_argument(
            '--uri',
            dest='uri',
            help=f"URI of Fatbuildr server (default: {DEFAULT_URI})",
        )

        # Unfortunately, Python 3.6 does support add_subparsers() required
        # attribute. The requirement is later handled with a AttributeError on
        # args.func to provide the same functionnal level.
        # This Python version conditionnal test can be removed when support of
        # Python 3.6 is dropped in Fatbuildr.
        if sys.version_info[1] >= 3 and sys.version_info[1] >= 7:
            subparsers = parser.add_subparsers(
                help='Action to perform', dest='action', required=True
            )
        else:
            subparsers = parser.add_subparsers(
                help='Action to perform', dest='action'
            )

        # Parser for the images command
        parser_images = subparsers.add_parser(
            'images', help='Manage build images'
        )

        parser_images.set_defaults(func=self._run_images)
        if sys.version_info[1] >= 3 and sys.version_info[1] >= 7:
            images_subparsers = parser_images.add_subparsers(
                help='Operation on image', dest='operation', required=True
            )
        else:
            images_subparsers = parser_images.add_subparsers(
                help='Action to perform', dest='operation'
            )
        # Sub-parser for images create
        parser_images_create = images_subparsers.add_parser(
            'create', help='Create format specific container image'
        )
        parser_images_create.add_argument(
            '-f',
            '--format',
            help='Create container image for this format',
        )
        parser_images_create.add_argument(
            '--force',
            action='store_true',
            help='Force creation of images even they already exist',
        )
        parser_images_create.add_argument(
            '--batch',
            action='store_true',
            help='Submit task in background',
        )

        # Sub-parser for images update
        parser_images_update = images_subparsers.add_parser(
            'update', help='Create format specific container image'
        )
        parser_images_update.add_argument(
            '-f',
            '--format',
            help='Update container image for this format',
        )
        parser_images_update.add_argument(
            '--batch',
            action='store_true',
            help='Submit task in background',
        )

        # Sub-parser for images shell
        parser_images_shell = images_subparsers.add_parser(
            'shell',
            help=(
                'Launch shell or execute command in format specific container '
                'image'
            ),
        )
        parser_images_shell.add_argument(
            '-f',
            '--format',
            help=(
                'Launch shell or execute command in this format specific '
                'container image'
            ),
        )
        parser_images_shell.add_argument(
            'command',
            help='Command to execute in format specific container image',
            nargs='*',
        )

        # Sub-parser for images env-create
        parser_images_env_create = images_subparsers.add_parser(
            'env-create', help='Create build environments'
        )
        parser_images_env_create.add_argument(
            '-f',
            '--format',
            help='Create build environments for this format',
        )
        parser_images_env_create.add_argument(
            '-d',
            '--distribution',
            help='Create build environments for this distribution',
        )
        parser_images_env_create.add_argument(
            '-a',
            '--architecture',
            help='Create build environments for this hardware architecture',
        )
        parser_images_env_create.add_argument(
            '--batch',
            action='store_true',
            help='Submit task in background',
        )

        # Sub-parser for images env-update
        parser_images_env_update = images_subparsers.add_parser(
            'env-update', help='Update build environments'
        )
        parser_images_env_update.add_argument(
            '-f',
            '--format',
            help='Update build environments for this format',
        )
        parser_images_env_update.add_argument(
            '-d',
            '--distribution',
            help='Update build environments for this distribution',
        )
        parser_images_env_update.add_argument(
            '-a',
            '--architecture',
            help='Update build environments for this hardware architecture',
        )
        parser_images_env_update.add_argument(
            '--batch',
            action='store_true',
            help='Submit task in background',
        )

        # Sub-parser for images env-shell
        parser_images_env_shell = images_subparsers.add_parser(
            'env-shell',
            help='Launch shell or execute command in build environment',
        )
        parser_images_env_shell.add_argument(
            '-f',
            '--format',
            help='Select build environment for this format',
        )
        parser_images_env_shell.add_argument(
            '-d',
            '--distribution',
            help='Select build environment for this distribution',
        )
        parser_images_env_shell.add_argument(
            '-a',
            '--architecture',
            help='Select build environment for this hardware architecture',
        )
        parser_images_env_shell.add_argument(
            'command',
            help='Command to execute in build environment',
            nargs='*',
        )

        # Parser for the keyring command
        parser_keyring = subparsers.add_parser(
            'keyring', help='Manage signing keyring'
        )
        parser_keyring.add_argument('--duration', help='New duration for renew')
        parser_keyring.add_argument(
            'operation',
            help='Operation on keyring (default: %(default)s)',
            nargs='?',
            choices=['show', 'export', 'create', 'renew'],
            default='show',
        )
        parser_keyring.set_defaults(func=self._run_keyring)

        # Parser for the build command
        parser_build = subparsers.add_parser('build', help='Submit new build')
        parser_build.add_argument(
            '-a', '--artifact', help='Artifact name', required=True
        )
        parser_build.add_argument(
            '-d', '--distribution', help='Distribution name'
        )
        parser_build.add_argument(
            '-f', '--format', help='Format of the artifact'
        )
        parser_build.add_argument(
            '--derivative',
            help='Distribution derivative (default: %(default)s)',
            default='main',
        )
        parser_build.add_argument(
            '-b',
            '--basedir',
            help='Artifacts definitions directory',
        )
        parser_build.add_argument(
            '-s', '--subdir', help='Artifact subdirectory'
        )
        parser_build.add_argument(
            '--sources',
            help=(
                'Generate artifact source archives using the source code in '
                'this directory.'
            ),
            nargs='*',
            default=[],
        )
        parser_build.add_argument(
            '--include-git-untracked',
            help=(
                'Include in generated artifact source archive files untracked '
                'in git repository.'
            ),
            action='store_true',
        )
        parser_build.add_argument('-n', '--name', help='Maintainer name')
        parser_build.add_argument('-e', '--email', help='Maintainer email')
        parser_build.add_argument('-m', '--msg', help='Build log message')
        parser_build.add_argument(
            '--batch',
            action='store_true',
            help='Submit task in background',
        )
        parser_build.add_argument(
            '-i',
            '--interactive',
            action='store_true',
            help='Launch build commands in interactive mode',
        )
        parser_build.set_defaults(func=self._run_build)

        # Parser for the list command
        parser_list = subparsers.add_parser('list', help='List tasks')
        parser_list.set_defaults(func=self._run_list)

        # Parser for the patches command
        parser_patches = subparsers.add_parser(
            'patches', help='Manage artifact patch queue'
        )
        parser_patches.add_argument(
            '-a', '--artifact', help='Artifact name', required=True
        )
        parser_patches.add_argument(
            '--derivative',
            help='Distribution derivative (default: %(default)s)',
            default='main',
        )
        parser_patches.add_argument(
            '-b',
            '--basedir',
            help='Artifacts definitions directory',
        )
        parser_patches.add_argument(
            '-s', '--subdir', help='Artifact subdirectory'
        )
        parser_patches.add_argument('-n', '--name', help='Maintainer name')
        parser_patches.add_argument('-e', '--email', help='Maintainer email')
        parser_patches.add_argument(
            '--sources',
            help=(
                'Generate artifact source archives using the source code in '
                'this directory.'
            ),
            nargs='*',
            default=[],
        )
        parser_patches.add_argument(
            '--include-git-untracked',
            help=(
                'Include in generated artifact source archive files  untracked '
                'in git repository.'
            ),
            action='store_true',
        )
        parser_patches.set_defaults(func=self._run_patches)

        # Parser for the watch command
        parser_watch = subparsers.add_parser('watch', help='Watch task')
        parser_watch.add_argument(
            'task',
            help='ID of task to watch (default: running task)',
            nargs='?',
        )
        parser_watch.set_defaults(func=self._run_watch)

        # Parser for the history command
        parser_history = subparsers.add_parser(
            'history', help='List history of tasks'
        )
        parser_history.add_argument(
            'operation',
            help='Operation on history (default: %(default)s)',
            nargs='?',
            choices=['purge', 'list'],
            default='list',
        )
        parser_history.add_argument(
            '--batch',
            action='store_true',
            help='Submit task in background',
        )

        parser_history.set_defaults(func=self._run_history)

        # Parser for the registry command
        parser_registry = subparsers.add_parser(
            'registry', help='Manage artifact registries'
        )
        parser_registry.add_argument(
            'operation',
            help='Operation on selected artifacts (default: %(default)s)',
            nargs='?',
            choices=['list', 'delete'],
            default='list',
        )
        parser_registry.add_argument(
            '-d', '--distribution', help='Distribution name', required=True
        )
        parser_registry.add_argument(
            '--derivative', help='Distribution derivative', default='main'
        )
        parser_registry.add_argument(
            '-a', '--artifact', help='Name of artifact'
        )

        parser_registry.set_defaults(func=self._run_registry)

        # Parser for the tokens command
        parser_tokens = subparsers.add_parser(
            'tokens', help='Manage REST API tokens'
        )
        parser_tokens.add_argument(
            'operation',
            help='Operation on tokens (default: %(default)s)',
            nargs='?',
            choices=['list', 'generate', 'save'],
            default='list',
        )
        parser_tokens.add_argument(
            '--uri', help='URI associated to saved token'
        )

        parser_tokens.set_defaults(func=self._run_tokens)

        args = parser.parse_args()

        logger.setup(args.debug or args.fulldebug, args.fulldebug)
        self.load(args)

        # Connection to fatbuildrd, initialized when needed in connection
        # property method.
        self._connection = None

        # Check action is provided in argument by checking default subparser
        # func is defined.
        if not hasattr(args, 'func'):
            parser.print_usage()
            logger.error("The action argument must be given")
            sys.exit(1)

        # Run the method corresponding to the provided action, catching optional
        # server, permission and runtime error returned by fatbuildrd.
        try:
            args.func(args)
        except FatbuildrServerPermissionError as err:
            logger.error("server permission error: %s", err)
            sys.exit(1)
        except FatbuildrServerError as err:
            logger.error("server error: %s", err)
            sys.exit(1)
        except FatbuildrArtifactError as err:
            logger.error("artifact error: %s", err)
            sys.exit(1)
        except FatbuildrRuntimeError as err:
            logger.error("runtime error: %s", err)
            sys.exit(1)

    @property
    def connection(self):
        """Returns the already established connection or creates a new
        connection and returns it."""
        if self._connection:
            return self._connection
        self._connection = ClientFactory.get(
            self.uri, ClientTokensManager(self.prefs.tokens_dir).load(self.uri)
        )
        return self._connection

    def load(self, args):
        """Register protocols and load user preferences, then set common
        parameters accordingly."""

        # load all tasks and exportable types structures in protocol
        register_protocols()

        # Load user preferences
        self.prefs = UserPreferences(args.preferences)

        # Set URI with args, prefs and default descending priority
        if args.uri is None:
            if self.prefs.uri is None:
                self.uri = DEFAULT_URI
            else:
                self.uri = self.prefs.uri
        else:
            self.uri = args.uri

        self.prefs.dump()

    def _run_images(self, args):
        logger.debug("running images task")

        # Check action is provided in argument by checking default subparser
        # func is defined.
        if not hasattr(args, 'operation'):
            # FIXME: print usage
            logger.error("The operation argument must be given")
            sys.exit(1)

        def select_formats():
            """Return the list of selected formats for the operation. If the
            distribution argument exists and is defined, check it matches the
            format argument if defined and return the format associated to this
            distribution. Else, if the argument is defined, check it is
            supported and select it. Otherwise, return the list of all supported
            formats."""
            supported_formats = self.connection.pipelines_formats()
            if hasattr(args, 'distribution') and args.distribution:
                dist_fmt = self.connection.pipelines_distribution_format(
                    args.distribution
                )
                # if format is also given, check it matches
                if args.format and args.format != dist_fmt:
                    logger.error(
                        "Specified format %s does not match the format "
                        "of the specified distribution %s",
                        args.format,
                        args.distribution,
                    )
                    sys.exit(1)
                return [dist_fmt]
            if args.format:
                # Check format provided by user in argument is supported by this
                # instance.
                if args.format not in supported_formats:
                    logger.error(
                        "Format %s is not supported by this instance",
                        args.format,
                    )
                    sys.exit(1)
                return [args.format]
            else:
                return supported_formats

        def select_build_environments(format):
            """Returns the list of selected build environments for the
            operation. If the distribution option is defined in the command
            line, it returns the build environment associated to this
            distribution and the given format. Otherwise, it returns the build
            environments associated to all distributions declared in instance
            pipelines for the given format."""
            if args.distribution:
                distributions = [args.distribution]
            else:
                distributions = self.connection.pipelines_format_distributions(
                    format
                )
                if not distributions:
                    logger.info("No distribution defined for %s image", format)
            result = []
            for distribution in distributions:
                env = self.connection.pipelines_distribution_environment(
                    distribution
                )
                if env is not None:
                    result.append(env)
                logger.debug(
                    "Build environments found for format %s: %s", format, env
                )
            return result

        def select_architectures():
            """Returns the list of selected architecture for the build
            environment operation. If the architecture option is defined in
            command line, it checks if the architecture is well declared in
            instance pipelines and returns this value. Otherwise, it returns the
            list of all architectures declared in instance pipelines."""
            available_architectures = self.connection.pipelines_architectures()
            logger.debug(
                "Architectures defined in pipelines: %s",
                available_architectures,
            )
            if args.architecture:
                if args.architecture not in available_architectures:
                    logger.error(
                        "Selected architecture %s is not available in this "
                        "instance pipelines",
                        args.architecture,
                    )
                    logger.info(
                        "Select an architecture among the architectures "
                        "available in this instance pipelines: %s",
                        ' '.join(available_architectures),
                    )
                    sys.exit(1)
                result = [args.architecture]
            else:
                result = available_architectures
                logger.debug("Selected architectures: %s", result)
            return result

        # check if operation is on images and run it
        if args.operation == 'create':
            for format in select_formats():
                self._submit_task(
                    self.connection.image_create,
                    f"{format} image creation",
                    args.batch,
                    format,
                    args.force,
                )
        elif args.operation == 'update':
            for format in select_formats():
                self._submit_task(
                    self.connection.image_update,
                    f"{format} image update",
                    args.batch,
                    format,
                )
        elif args.operation == 'shell':
            # Verify that only one format is selected at this stage or fail.
            selected_formats = select_formats()
            try:
                assert len(selected_formats) == 1
            except AssertionError:
                logger.error(
                    "Unable to define container image for the shell among {%s}"
                    "formats",
                    ','.join(selected_formats),
                )
                logger.info(
                    "Please use --format filter to select the container image"
                )
                sys.exit(1)

            selected_format = selected_formats[0]
            self._submit_task(
                self.connection.image_shell,
                f"{selected_format} image shell",
                False,
                selected_format,
                os.getenv('TERM'),
                args.command,
                interactive=True,
            )
        elif args.operation == 'env-create':
            for format in select_formats():
                for env in select_build_environments(format):
                    for architecture in select_architectures():
                        self._submit_task(
                            self.connection.image_environment_create,
                            f"{format} {env}-{architecture} build "
                            "environment creation",
                            args.batch,
                            format,
                            env,
                            architecture,
                        )
        elif args.operation == 'env-update':
            for format in select_formats():
                for env in select_build_environments(format):
                    for architecture in select_architectures():
                        self._submit_task(
                            self.connection.image_environment_update,
                            f"{format} {env}-{architecture} build "
                            "environment update",
                            args.batch,
                            format,
                            env,
                            architecture,
                        )
        elif args.operation == 'env-shell':
            selected_formats = select_formats()
            if args.distribution:
                dist_fmt = self.connection.pipelines_distribution_format(
                    args.distribution
                )
                # if format is also given, check it matches
                if args.format and args.format != dist_fmt:
                    logger.error(
                        "Specified format %s does not match the format "
                        "of the specified distribution %s",
                        args.format,
                        args.distribution,
                    )
                    sys.exit(1)
                selected_formats = [dist_fmt]
            # Verify that only one format is selected at this stage or fail.
            try:
                assert len(selected_formats) == 1
            except AssertionError:
                logger.error(
                    "Unable to define the format for the build environment "
                    "shell among {%s} formats",
                    ','.join(selected_formats),
                )
                logger.info(
                    "Please use --format or --distribution filters to select "
                    "the build environment"
                )
                sys.exit(1)
            selected_format = selected_formats[0]
            selected_envs = select_build_environments(selected_format)
            # Verify that only one build environment is selected at this
            # stage or fail.
            try:
                assert len(selected_envs) == 1
            except AssertionError:
                logger.error(
                    "Unable to define the build environment for the "
                    "shell among {%s}",
                    ','.join(selected_envs),
                )
                logger.info(
                    "Please use --distribution filter to select a "
                    "specific build environment"
                )
                sys.exit(1)
            selected_env = selected_envs[0]
            selected_architectures = select_architectures()
            # Verify that only one hardware architecture is selected at thi
            # stage or fail.
            try:
                assert len(selected_architectures) == 1
            except AssertionError:
                logger.error(
                    "Unable to define the hardware architecture for "
                    "the shell among {%s}",
                    ','.join(selected_architectures),
                )
                logger.info(
                    "Please use --architecture filter to select a "
                    "specific build environment hardware architecture "
                    "for running the shell"
                )
                sys.exit(1)
            selected_architecture = selected_architectures[0]
            self._submit_task(
                self.connection.image_environment_shell,
                f"{selected_format} {selected_env}-{selected_architecture} "
                "build environment shell",
                False,  # batch
                selected_format,
                selected_env,
                selected_architecture,
                os.getenv('TERM'),
                args.command,
                interactive=True,
            )

    def _run_keyring(self, args):
        logger.debug("running keyring operation")
        if args.operation == 'create':
            task_id = self.connection.keyring_create()
            print(f"Submitted keyring creation task {task_id}")
        elif args.operation == 'renew':
            if not args.duration:
                logger.error(
                    "Duration must be given to renew keyring, type '%s '"
                    "keyring --help' for details",
                    progname(),
                )
                sys.exit(1)
            task_id = self.connection.keyring_renew(args.duration)
            print(f"Submitted keyring renewal task {task_id}")
        elif args.operation == 'show':
            keyring = self.connection.keyring()
            if keyring:
                keyring.report()
            else:
                print(f"No keyring available on URI {self.uri}")
        elif args.operation == 'export':
            print(self.connection.keyring_export(), end='')
        else:
            NotImplementedError(
                f"Unsupported keyring operation {args.operation}"
            )

    def _get_basedir(self, args):
        """Returns the basedir based on args and prefs descending priority, or
        fail with return code 1 and error message."""
        if args.basedir is None:
            if self.prefs.basedir is None:
                print(
                    "Base directory must be defined for build operations, "
                    "either with --basedir argument or through user "
                    "preferences file."
                )
                sys.exit(1)
            else:
                return self.prefs.basedir
        else:
            return args.basedir

    def _get_subdir(self, args):
        """Returns the subdir, which defaults to artifact name if not provided
        in arguments."""
        if args.subdir is None:
            return args.artifact
        else:
            return args.subdir

    def _get_apath(self, args):
        """Returns the Path to the artifact definition according to the
        provided command line args."""
        return Path(self._get_basedir(args), self._get_subdir(args))

    def _get_user_name(self, args):
        """Returns the user name based on args and prefs descending priority,
        or fail with return code 1 and error message."""
        if args.name is None:
            if self.prefs.user_name is None:
                print(
                    "The user name be defined for build operations, "
                    "either with --name argument or through user "
                    "preferences file."
                )
                sys.exit(1)
            else:
                return self.prefs.user_name
        else:
            return args.name

    def _get_user_email(self, args):
        """Returns the user email based on args and prefs descending priority,
        or fail with return code 1 and error message."""
        if args.email is None:
            if self.prefs.user_email is None:
                print(
                    "The user email must be defined for build operations, "
                    "either with --email argument or through user "
                    "preferences file."
                )
                sys.exit(1)
            else:
                return self.prefs.user_email
        else:
            return args.email

    def _get_format_distribution(self, defs, args):
        """Defines format and distribution of the build or pq, given the
        provided arguments, artifact definition and server pipelines. It
        tries to guess as much missing information as possible. It also
        performs some coherency checks, the program is left with return code 1
        and a meaningfull message when error is detected."""

        format = None
        distribution = None

        if args.distribution:
            distribution = args.distribution
            dist_fmt = self.connection.pipelines_distribution_format(
                args.distribution
            )
            # if format is also given, check it matches
            if args.format and args.format != dist_fmt:
                logger.error(
                    "Specified format %s does not match the format "
                    "of the specified distribution %s",
                    args.format,
                    args.distribution,
                )
                sys.exit(1)
            format = dist_fmt
        elif args.format is None:
            # distribution and format have not been specified, check format
            # supported by the artifact.
            supported_fmts = defs.supported_formats
            # check if there is not more than one supported format for this
            # artifact
            if len(supported_fmts) > 1:
                logger.error(
                    "There is more than one supported format for "
                    "artifact %s, at least the format must be "
                    "specified",
                    args.artifact,
                )
                sys.exit(1)
            if supported_fmts:
                format = supported_fmts[0]
                logger.debug(
                    "Format %s has been selected for artifact %s",
                    format,
                    args.artifact,
                )

        if not format:
            logger.error(
                "Unable to define format of artifact %s, either the "
                "distribution or the format must be specified",
                args.artifact,
            )
            sys.exit(1)
        elif not args.distribution:
            format_dists = self.connection.pipelines_format_distributions(
                format
            )
            # check if there is not more than one distribution for this format
            if len(format_dists) > 1:
                logger.error(
                    "There is more than one distribution for the "
                    "format %s in pipelines definition, the "
                    "distribution must be specified",
                    format,
                )
                sys.exit(1)
            distribution = format_dists[0]
            logger.debug(
                "Distribution %s has been selected for format %s",
                distribution,
                format,
            )

        # check artifact accepts this format
        if format not in defs.supported_formats:
            logger.error(
                "Format %s is not accepted by artifact %s",
                format,
                args.artifact,
            )
            sys.exit(1)

        # check artifact accepts this derivative
        if args.derivative not in defs.derivatives:
            logger.error(
                "Derivative %s is not accepted by artifact %s",
                args.derivative,
                args.artifact,
            )
            sys.exit(1)

        # check format is accepted for this derivative
        if format not in self.connection.pipelines_derivative_formats(
            args.derivative
        ):
            logger.error(
                "Derivative %s does not accept format %s",
                args.derivative,
                format,
            )
            sys.exit(1)

        return (format, distribution)

    def _build_local_sources(
        self, defs, artifact, derivative, sources, include_git_untracked
    ):
        results = []
        for source in sources:
            if '#' in source:
                (source_id, version_path) = source.split('#', 1)
            else:
                source_id = artifact
                version_path = source
            # Check the source ID is defined and available in artifact
            # definition file.
            if source_id not in defs.defined_sources:
                raise FatbuildrRuntimeError(
                    f"Source ID {source_id} not found in artifact definition "
                    "file"
                )
            # Check the source ID has not already been loaded with a previous
            # source option.
            if source_id in [_source.id for _source in results]:
                raise FatbuildrRuntimeError(
                    "Conflict between multiple sources sharing the same ID "
                    f"{source_id}"
                )
            if '@' in version_path:
                (source_version, source_dir) = version_path.split('@', 1)
            else:
                source_version = defs.source(source_id).version(derivative)
                source_dir = version_path
            results.append(
                WireSourceArchive(
                    source_id,
                    prepare_source_tarball(
                        source_id,
                        Path(source_dir),
                        source_version,
                        self.connection.scheme == 'dbus',
                        include_git_untracked,
                    ),
                )
            )
        return results

    def _run_build(self, args):
        logger.debug(
            "running build for artifact: %s uri: %s", args.artifact, self.uri
        )

        # check user ask for interactive mode with non dbus instance
        if args.interactive and self.connection.scheme != 'dbus':
            logger.warning(
                "Interactive mode is only supported with D-Bus instances, "
                "fallback in non-interactive mode"
            )
            args.interactive = False

        # If user asks for interactive build also force deactivation of batch
        # feature, otherwise interactive would be pointless.
        if args.interactive:
            args.batch = False

        apath = self._get_apath(args)
        defs = ArtifactDefs(apath, args.artifact)  # load generic artifact defs

        user_name = self._get_user_name(args)
        user_email = self._get_user_email(args)

        # Set build_msg with args, prefs descending priority, or fail
        if args.msg is None:
            if self.prefs.message is None:
                print(
                    "The build message must be defined for build operations, "
                    "either with --msg argument or through user "
                    "preferences file."
                )
                sys.exit(1)
            else:
                build_msg = self.prefs.message
        else:
            build_msg = args.msg

        (format, distribution) = self._get_format_distribution(defs, args)

        architectures = self.connection.pipelines_architectures()
        logger.debug("Architectures defined in pipelines: %s", architectures)
        arch_dependent = ArtifactDefsFactory.get(
            apath, args.artifact, format
        ).architecture_dependent
        logger.debug(
            "Artifact %s is %sarchitecture dependent",
            args.artifact,
            'NOT ' if not arch_dependent else '',
        )

        if not arch_dependent:
            # If the artifact is artifact is architecture independant,
            # arbitrarily pick up the first architecture defined in
            # pipelines.
            selected_architectures = [architectures[0]]
        else:
            selected_architectures = architectures

        logger.debug("Selected architectures: %s", selected_architectures)

        sources = self._build_local_sources(
            defs,
            args.artifact,
            args.derivative,
            args.sources,
            args.include_git_untracked,
        )

        try:
            # Prepare artifact definition tarball, in fatbuildrd runtime
            # directory if connected to fatbuildrd through dbus.
            tarball = prepare_tarball(apath, self.connection.scheme == 'dbus')
            self._submit_task(
                self.connection.build,
                f"{args.artifact} build",
                args.batch,
                format,
                distribution,
                selected_architectures,
                args.derivative,
                args.artifact,
                user_name,
                user_email,
                build_msg,
                tarball,
                sources,
                args.interactive,
                interactive=args.interactive,
            )
        except FatbuildrRuntimeError as err:
            logger.error("Error while submitting build: %s", err)
            sys.exit(1)

    def _run_list(self, args):
        logger.debug("running list")
        try:
            running = self.connection.running()
            if running:
                print("Running tasks:")
                running.report()
            else:
                print("No running task")

            queue = self.connection.queue()
            if queue:
                print("Pending tasks:")
                for task in queue:
                    task.report()

        except FatbuildrRuntimeError as err:
            logger.error("Error while listing tasks: %s", err)
            sys.exit(1)

    def _run_patches(self, args):

        apath = self._get_apath(args)
        defs = ArtifactDefs(apath, args.artifact)
        user_name = self._get_user_name(args)
        user_email = self._get_user_email(args)
        sources = self._build_local_sources(
            defs,
            args.artifact,
            args.derivative,
            args.sources,
            args.include_git_untracked,
        )

        patch_queue = PatchQueue(
            apath,
            args.derivative,
            args.artifact,
            defs,
            user_name,
            user_email,
            sources,
        )
        patch_queue.run()

        # If source tarballs have been generated, remove them before leaving.
        for source in sources:
            logger.debug("Removing generated source tarball %s", source.path)
            source.path.unlink()

    def _submit_task(self, caller, task_name, batch, *args, interactive=False):
        task_id = caller(*args)
        print(f"Submitted {task_name} task {task_id}")
        if not batch:
            self._watch_task(task_id, interactive)

    def _watch_task(self, task_id, interactive):
        task = self.connection.get(task_id)

        warned_pending = False
        # if build is pending, wait
        while task.state == 'pending':
            if not warned_pending:
                logger.info(
                    "Task %s is pending, waiting for the task to start.",
                    task.id,
                )
                warned_pending = True
            time.sleep(1)
            # poll task state again
            task = self.connection.get(task_id)
        try:
            if interactive:
                self.connection.attach(task)
            else:
                tty_console_renderer(self.connection.watch(task))
        except KeyboardInterrupt:
            # Leave gracefully after a keyboard interrupt (eg. ^c)
            logger.debug("Received keyboard interrupt, leaving.")
        except BrokenPipeError:
            # Stop if hit a broken pipe. It could happen when watch is given to
            # `head` for example.
            pass

    def _run_watch(self, args):
        if not args.task:
            running = self.connection.running()
            if not running:
                logger.error(
                    "No running task found, please give a task ID to watch."
                )
                sys.exit(1)
            task_id = running.id
        else:
            task_id = args.task
        self._watch_task(task_id, interactive=False)

    def _run_history(self, args):
        if args.operation == 'list':
            history = self.connection.history(10)
            if not history:
                print("No task found in history")
                return
            print("Tasks history:")
            for task in history:
                task.report()
        elif args.operation == 'purge':
            self._submit_task(
                self.connection.history_purge, 'tasks history purge', args.batch
            )
        else:
            NotImplementedError(
                f"Unsupported history operation {args.operation}"
            )

    def _run_registry(self, args):
        _fmt = self.connection.pipelines_distribution_format(args.distribution)
        artifacts = self.connection.artifacts(
            _fmt, args.distribution, args.derivative
        )
        if args.artifact:
            # filter out other artifact names
            artifacts = [
                artifact
                for artifact in artifacts
                if args.artifact in artifact.name
            ]
        if not artifacts:
            print(
                f"No artifact found in {_fmt} distribution {args.distribution} "
                f"derivative {args.derivative}"
            )
            return
        if args.operation == 'list':
            print(
                f"Artifacts found for {_fmt} distribution {args.distribution} "
                f"derivative {args.derivative}:"
            )
            for artifact in artifacts:
                artifact.report()
        elif args.operation == 'delete':
            for artifact in artifacts:
                task_id = self.connection.delete_artifact(
                    _fmt,
                    args.distribution,
                    args.derivative,
                    artifact,
                )
                print(
                    f"Submitted artifact {artifact.name} deletion task "
                    f"{task_id}"
                )

    def _run_tokens(self, args):
        if args.operation == 'list':
            for token in ClientTokensManager(self.prefs.tokens_dir).tokens():
                print("token:\n  " + '\n  '.join(str(token).split('\n')))
        elif args.operation == 'generate':
            print(self.connection.token_generate())
        elif args.operation == 'save':
            if not args.uri:
                logger.error(
                    "The URI to associate with the token is not defined"
                )
                logger.info("Please use --uri option to define the token URI")
                sys.exit(1)
            token = sys.stdin.readline()
            ClientTokensManager(self.prefs.tokens_dir).save(self.uri, token)
