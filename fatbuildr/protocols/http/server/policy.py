#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
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

import configparser
import grp

try:
    from functools import cached_property
except ImportError:
    # For Python 3.[6-7] compatibility. The dependency to cached_property
    # external library is not declared in setup.py, it is added explicitely in
    # packages codes only for distributions stuck with these old versions of
    # Python.
    #
    # This try/except block can be removed when support of Python < 3.8 is
    # dropped in Fatbuildr.
    from cached_property import cached_property

from ....errors import FatbuildrRuntimeError
from ....log import logr

logger = logr(__name__)


class PolicyRole:
    def __init__(self, name, members, actions):
        self.name = name
        self.members = members
        self.actions = actions

    def __repr__(self):
        return (
            f"{self.name} [ members: {self.members}, actions: {self.actions} ]"
        )


class PolicyManager:
    ANONYMOUS = 'anonymous'

    def __init__(self, conf):
        self.roles = set()
        # If the site policy exists, load this file. Otherwise load default
        # vendor policy.
        if conf.run.policy.exists():
            logger.info("Loading site policy %s", conf.run.policy)
            self._load_policy(conf.run.policy)
        else:
            logger.info("Loading vendor policy %s", conf.run.vendor_policy)
            self._load_policy(conf.run.vendor_policy)

    def _load_policy(self, path):
        """Loads the set of PolicyRoles defined in file pointed by the given
        path."""
        data = configparser.ConfigParser(allow_no_value=True)
        with open(path) as fh:
            data.read_file(fh)
        for opt in data.options('roles'):
            actions = self._expand_actions(data.get(opt, 'actions'))
            if opt == self.ANONYMOUS:
                members = None
            else:
                members = self._expand_members(data.get('roles', opt))
            self.roles.add(PolicyRole(opt, members, actions))

    def _expand_actions(self, actions_str):
        """Returns the set of actions declared in comma-separated list provided
        in actions_str argument. If an item is prefixed by @, the set is
        expanded with the actions of the role name that follows."""
        actions = set()
        for action in actions_str.split(','):
            if action.startswith('@'):
                actions.union(self.role_actions(action[1:]))
            else:
                actions.add(action)
        return actions

    def _expand_members(self, members_str):
        """Returns the set of members declared in comma-separated list provided
        in members_str argument."""
        return set(members_str.split(','))

    def role_actions(self, role):
        """Returns the set of actions allowed the to given role. Raises
        FatbuildrRuntimeError if the role is not found in policy."""
        for role in self.roles:
            if role.name == role:
                return role.actions

        return FatbuildrRuntimeError(f"Role {role} not found in policy")

    @cached_property
    def allow_anonymous(self):
        """Returns True if the anonymous role is declared in policy, False
        otherwise."""
        for role in self.roles:
            if role.name == self.ANONYMOUS:
                return True
        return False

    def _user_roles(self, user):
        """Returns the set of roles associated to a given user name."""
        roles = set()
        for role in self.roles:
            if role.members is None:  # anonymous
                roles.add(role)
            else:
                for member in role.members:
                    if member == user or (
                        member.startswith('@')
                        and user in grp.getgrnam(member[1:]).gr_mem
                    ):
                        roles.add(role)
        logger.debug("Found the following roles for user %s: %s", user, roles)
        return roles

    def validate_anonymous_action(self, action):
        """Returns True if the given action is allowed for anonymous role, False
        otherwise."""
        for role in self.roles:
            if role.name == self.ANONYMOUS and action in role.actions:
                return True
        return False

    def validate_user_action(self, user, action):
        """Returns True if the given action is allowed for the given user, False
        otherwise."""
        for role in self._user_roles(user):
            if action in role.actions:
                logger.debug(
                    "Token for user %s is permitted to perform action %s",
                    user,
                    action,
                )
                return True
        logger.warn(
            "Token for user %s is not authorized to perform action %s",
            user,
            action,
        )
        return False
