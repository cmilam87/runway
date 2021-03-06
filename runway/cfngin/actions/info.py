"""CFNgin info action."""
import logging

from .. import exceptions
from .base import BaseAction

LOGGER = logging.getLogger(__name__)


class Action(BaseAction):
    """Get information on CloudFormation stacks.

    Displays the outputs for the set of CloudFormation stacks.

    """

    def run(self, **kwargs):
        """Get information on CloudFormation stacks."""
        LOGGER.info('Outputs for stacks: %s', self.context.get_fqn())
        if not self.context.get_stacks():
            LOGGER.warning('WARNING: No stacks detected (error in config?)')
        for stack in self.context.get_stacks():
            provider = self.build_provider(stack)

            try:
                provider_stack = provider.get_stack(stack.fqn)
            except exceptions.StackDoesNotExist:
                LOGGER.info('Stack "%s" does not exist.', stack.fqn,)
                continue

            LOGGER.info('%s:', stack.fqn)
            if 'Outputs' in provider_stack:
                for output in provider_stack['Outputs']:
                    LOGGER.info(
                        '\t%s: %s',
                        output['OutputKey'],
                        output['OutputValue']
                    )
