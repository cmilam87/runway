"""Test deploying a base line static site."""
from runway.util import change_dir

from integration_tests.test_staticsite.test_staticsite import StaticSite
from integration_tests.util import run_command


class TestBasicSite(StaticSite):
    """Test deploying a base line static site."""

    TEST_NAME = __name__
    module_dir = 'basic-site'

    def deploy(self):
        """Deploy provider."""
        self.copy_fixture(self.module_dir)
        self.copy_runway('basic-site')
        with change_dir(self.staticsite_test_dir):
            return run_command(['runway', 'deploy'])

    def run(self):
        """Run tests."""
        self.clean()
        self.set_env_var('CI', '1')
        assert self.deploy() == 0, '{}: Basic Site failed'.format(__name__)

    def teardown(self):
        self.logger.info('Tearing down: %s', self.TEST_NAME)
        self.delete_venv(self.module_dir)
        with change_dir(self.staticsite_test_dir):
            run_command(['runway', 'destroy'])
        self.clean()
        self.unset_env_var('CI')
