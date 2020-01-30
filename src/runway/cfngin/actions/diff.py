"""CFNgin diff action."""
import logging
from operator import attrgetter

from .. import exceptions
from ..status import (COMPLETE, INTERRUPTED, NotSubmittedStatus,
                      NotUpdatedStatus)
from . import build
from .base import build_walker, plan

LOGGER = logging.getLogger(__name__)


class DictValue(object):
    """Used to create a diff of two dictionaries."""

    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNMODIFIED = "UNMODIFIED"

    formatter = "%s%s = %s"

    def __init__(self, key, old_value, new_value):
        """Instantiate class."""
        self.key = key
        self.old_value = old_value
        self.new_value = new_value

    def __eq__(self, other):
        """Compare if self is equal to another object."""
        return self.__dict__ == other.__dict__

    def changes(self):
        """Return changes to represent the diff between old and new value.

        Returns:
            list: [string] representation of the change (if any)
                between old and new value

        """
        output = []
        if self.status() is self.UNMODIFIED:
            output = [self.formatter % (' ', self.key, self.old_value)]
        elif self.status() is self.ADDED:
            output.append(self.formatter % ('+', self.key, self.new_value))
        elif self.status() is self.REMOVED:
            output.append(self.formatter % ('-', self.key, self.old_value))
        elif self.status() is self.MODIFIED:
            output.append(self.formatter % ('-', self.key, self.old_value))
            output.append(self.formatter % ('+', self.key, self.new_value))
        return output

    def status(self):
        """Status of changes between the old value and new value."""
        if self.old_value == self.new_value:
            return self.UNMODIFIED
        if self.old_value is None:
            return self.ADDED
        if self.new_value is None:
            return self.REMOVED
        return self.MODIFIED


def diff_dictionaries(old_dict, new_dict):
    """Calculate the diff two single dimension dictionaries.

    Args:
        old_dict(Dict[Any, Any]): Old dictionary.
        new_dict(Dict[Any, Any]): New dictionary.

    Returns:
        Tuple[int, List[DictValue]]: Number of changed records and the
            DictValue object containing the changes.

    """
    old_set = set(old_dict)
    new_set = set(new_dict)

    added_set = new_set - old_set
    removed_set = old_set - new_set
    common_set = old_set & new_set

    changes = 0
    output = []
    for key in added_set:
        changes += 1
        output.append(DictValue(key, None, new_dict[key]))

    for key in removed_set:
        changes += 1
        output.append(DictValue(key, old_dict[key], None))

    for key in common_set:
        output.append(DictValue(key, old_dict[key], new_dict[key]))
        if str(old_dict[key]) != str(new_dict[key]):
            changes += 1

    output.sort(key=attrgetter("key"))
    return changes, output


def format_params_diff(parameter_diff):
    """Handle the formatting of differences in parameters.

    Args:
        parameter_diff (List[DictValues]): A list of DictValues detailing the
            differences between two dicts returned by
            :func:`diff_dictionaries`.

    Returns:
        str: A formatted string that represents a parameter diff

    """
    params_output = '\n'.join([line for v in parameter_diff
                               for line in v.changes()])
    return """--- Old Parameters
+++ New Parameters
******************
%s\n""" % params_output


def diff_parameters(old_params, new_params):
    """Compare the old vs. new parameters and returns a "diff".

    If there are no changes, we return an empty list.

    Args:
        old_params(Dict[Any, Any]): old paramters
        new_params(Dict[Any, Any]): new parameters

    Returns:
        List[DictValue]: A list of differences.

    """
    changes, diff = diff_dictionaries(old_params, new_params)
    if changes == 0:
        return []
    return diff


class Action(build.Action):
    """Responsible for diffing CloudFormation stacks in AWS and locally.

    Generates the build plan based on stack dependencies (these dependencies
    are determined automatically based on references to output values from
    other stacks).

    The plan is then used to create a changeset for a stack using a
    generated template based on the current config.

    """

    def _diff_stack(self, stack, **_kwargs):
        """Handle diffing a stack in CloudFormation vs our config."""
        if self.cancel.wait(0):
            return INTERRUPTED

        if not build.should_submit(stack):
            return NotSubmittedStatus()

        if not build.should_update(stack):
            return NotUpdatedStatus()

        provider = self.build_provider(stack)
        tags = build.build_stack_tags(stack)

        stack.resolve(self.context, provider)
        parameters = self.build_parameters(stack)

        try:
            outputs = provider.get_stack_changes(
                stack, self._template(stack.blueprint), parameters, tags
            )
            stack.set_outputs(outputs)
        except exceptions.StackDidNotChange:
            LOGGER.info('No changes: %s', stack.fqn)

        return COMPLETE

    def _generate_plan(self, tail=False):
        return plan(
            description="Diff stacks",
            stack_action=self._diff_stack,
            tail=self._tail_stack if tail else None,
            context=self.context)

    def run(self, **kwargs):
        """Kicks off the diffing of the stacks in the stack_definitions."""
        action_plan = self._generate_plan()
        action_plan.outline(logging.DEBUG)
        if action_plan.keys():
            LOGGER.info("Diffing stacks: %s", ", ".join(action_plan.keys()))
        else:
            LOGGER.warning('WARNING: No stacks detected (error in config?)')
        walker = build_walker(kwargs.get('concurrency', 0))
        action_plan.execute(walker)

    def pre_run(self, **kwargs):
        """Do nothing."""

    def post_run(self, **kwargs):
        """Do nothing."""
