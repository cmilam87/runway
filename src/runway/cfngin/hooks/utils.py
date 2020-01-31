"""Hook utils."""
import collections
import errno
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager

from runway.util import load_object_from_string, change_dir

LOGGER = logging.getLogger(__name__)


def filter_commands(commands):
    """Remove empty commands."""
    return [cmd for cmd in commands if cmd and len(cmd) > 0]


def merge_commands(commands):
    """Merge command lists."""
    cmds = filter_commands(commands)
    if not cmds:
        raise ValueError('Expected at least one non-empty command')
    if len(cmds) == 1:
        return cmds[0]

    script = ' && '.join([shlex.quote(cmd) for cmd in cmds])
    return ['/bin/sh', '-c', script]


def run_command(cmd_list, cwd=os.getcwd(), stdout=sys.stdout):
    """Run command."""
    try:
        subprocess.check_call(cmd_list, cwd=cwd, stdout=stdout)
    except OSError as err:
        if err.errno == errno.ENOENT:
            LOGGER.error('%s is not installed!', cmd_list[0])
        raise err


class Docker(object):
    """Docker options.

    Args:
        dockerizePip (Union(str, bool)): Whether or not to use pip inside docker container.
            Valid options are True/False or the string 'non-linux'.
        runtime (str): The runtime use to find a suitable docker image.
            Example: 'python3.7'
            Image:   'lambdaci/lambda:build-{runtime}'
        dockerImage (str): The name of the docker image to use to run pip.
        dockerFile (str): The docker file to use when creating docker image. Can be a
            relative or absolute path.
    """

    def __init__(self,
                 dockerize_pip,
                 runtime,
                 docker_image=None,
                 docker_file=None):
        if not runtime and not docker_image:
            raise ValueError('runtime is required when no docker image is specified')

        self.runtime = runtime

        if dockerize_pip == 'non-linux':
            self.dockerize_pip = sys.platform.lower() != 'linux'
        else:
            self.dockerize_pip = dockerize_pip

        if docker_image and docker_file:
            raise ValueError('You can provide a dockerImage or a dockerFile'
                             ' option, not both')

        if docker_file:
            self.docker_file = docker_file

        default_image = 'lambci/lambda:build-%s' % runtime
        self.image = docker_image or default_image

    @staticmethod
    def get_uid(bind_path):
        """Get UID of docker process.

        Args:
            bind_path (str): Absolute path to mount in docker.
        """
        output = subprocess.check_output(
            ['docker', 'run', '--rm',
             '-v', '%s:/test' % bind_path, 'alpine',
             'stat', '-c', '%u', '/bin/sh'])
        return output.decode().strip()

    @staticmethod
    def try_bind_path(path):
        """Try mounting volume path in docker.

        Args:
            path (str): Absolute path to test volume mounting.
        """
        try:
            output = subprocess.check_output([
                'docker',
                'run',
                '--rm',
                '-v',
                '%s:/test', % path
                'alpine',
                'ls',
                '/test/requirements.txt'
            ]).decode().strip()
            return output == '/test/requirements.txt'
        except subprocess.CalledProcessError as err:
            LOGGER.debug(err)
            return False

    @staticmethod
    def get_bind_path(service_path):
        """Find suitable volume path for Docker for Windows.

        Args:
            service_path (str): Absolute path of the volume to mount in docker.
        """
        if sys.platform.lower() != 'win32':
            return service_path

        bind_paths = []
        base_bind_path = re.sub(r'\\([^\s])', '/$1', service_path)

        bind_paths.append(base_bind_path)
        if base_bind_path.startswith('/mnt/'):
            # cygwin "/mnt/C/users/..."
            base_bind_path = re.sub('^/mnt/', '/', base_bind_path)
        if base_bind_path[1] == ':':
            # normal windows "c:/users/..."
            drive = base_bind_path[0]
            path = base_bind_path[3:]
        elif base_bind_path[0] == '/' and base_bind_path[2] == '/':
            # gitbash "/c/users/..."
            drive = base_bind_path[1]
            path = base_bind_path.substring[3:]
        else:
            raise ValueError('Unknown path format'
                             '%s...' % base_bind_path[10:])

        # Docker Toolbox (seems like Docker for Windows can support this too)
        bind_paths.append('/%s/%s' % (drive.lower(), path))
        # Docker for Windows
        bind_paths.append('%s:/%s' % (drive.lower(), path))
        # other options just in case
        bind_paths.append('/%s/%s' % (drive.upper(), path))
        bind_paths.append('/mnt/%s/%s' % (drive.lower(), path))
        bind_paths.append('/mnt/%s/%s' % (drive.upper(), path))
        bind_paths.append('%s:/%s' % (drive.upper(), path))

        for bind_path in bind_paths:
            if Docker.try_bind_path(bind_path):
                return bind_path

        raise ValueError('Unable to find good bind path format')

    def build_image(self):
        """Build custom docker image using docker file."""
        image_name = 'cfngin-custom'
        options = ['build', '-f', self.docker_file, '-t', image_name]
        run_command(['docker'] + options)
        self.image = image_name


@contextmanager
def tempdir():
    """Create temp directory and cleanup."""
    dirpath = tempfile.mkdtemp()

    with change_dir(dirpath):
        yield dirpath
    shutil.rmtree(dirpath)


def full_path(path):
    """Return full path."""
    return os.path.abspath(os.path.expanduser(path))


def handle_hooks(stage, hooks, provider, context):
    """Handle pre/post_build hooks.

    These are pieces of code that we want to run before/after the builder
    builds the stacks.

    Args:
        stage (str): The current stage (pre_run, post_run, etc).
        hooks (List[:class:`runway.cfngin.config.Hook`]): Hooks to execute.
        provider (:class:`runway.cfngin.providers.base.BaseProvider`): Provider
            instance.
        context (:class:`runway.cfngin.context.Context`): Context instance.

    """
    if not hooks:
        LOGGER.debug("No %s hooks defined.", stage)
        return

    hook_paths = []
    for i, hook in enumerate(hooks):
        try:
            hook_paths.append(hook.path)
        except KeyError:
            raise ValueError("%s hook #%d missing path." % (stage, i))

    LOGGER.info("Executing %s hooks: %s", stage, ", ".join(hook_paths))
    for hook in hooks:
        data_key = hook.data_key
        required = hook.required
        kwargs = hook.args or {}
        enabled = hook.enabled
        if not enabled:
            LOGGER.debug("hook with method %s is disabled, skipping",
                         hook.path)
            continue
        try:
            method = load_object_from_string(hook.path)
        except (AttributeError, ImportError):
            LOGGER.exception("Unable to load method at %s:", hook.path)
            if required:
                raise
            continue
        try:
            result = method(context=context, provider=provider, **kwargs)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Method %s threw an exception:", hook.path)
            if required:
                raise
            continue
        if not result:
            if required:
                LOGGER.error("Required hook %s failed. Return value: %s",
                             hook.path, result)
                sys.exit(1)
            LOGGER.warning("Non-required hook %s failed. Return value: %s",
                           hook.path, result)
        else:
            if isinstance(result, collections.Mapping):
                if data_key:
                    LOGGER.debug("Adding result for hook %s to context in "
                                 "data_key %s.", hook.path, data_key)
                    context.set_hook_data(data_key, result)
                else:
                    LOGGER.debug("Hook %s returned result data, but no data "
                                 "key set, so ignoring.", hook.path)
