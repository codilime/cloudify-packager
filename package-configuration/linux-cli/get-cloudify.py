########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

# Install Cloudify on Debian and Ubuntu
# apt-get update
# apt-get install -y curl
# curl -L https://www.dropbox.com/s/ibwdmqhwnf4bewc/get-cloudify.py -o get-cloudify.py && python get-cloudify.py -f  # NOQA

# Install Cloudify on Arch Linux
# pacman -Syu --noconfirm
# pacman-db-upgrade
# pacman -S python2 --noconfirm
# curl -L https://www.dropbox.com/s/ibwdmqhwnf4bewc/get-cloudify.py -o get-cloudify.py && python2 get-cloudify.py -f --pythonpath=python2 # NOQA

# Install Cloudify on CentOS/RHEL
# yum -y update
# yum groupinstall -y development
# yum install -y zlib-dev openssl-devel sqlite-devel bzip2-devel wget gcc tar
# wget http://www.python.org/ftp/python/2.7.6/Python-2.7.6.tgz
# tar -xzvf Python-2.7.6.tgz
# cd Python-2.7.6
# ./configure --prefix=/usr/local && make && make altinstall
# curl -L https://www.dropbox.com/s/ibwdmqhwnf4bewc/get-cloudify.py -o get-cloudify.py && python2.7 get-cloudify.py --pythonpath=python2.7 -f # NOQA

# Install Cloudify on Windows (Python 32/64bit)
# Install Python 2.7.x 32/64bit from https://www.python.org/downloads/release/python-279/  # NOQA
# Make sure that when you install, you choose to add Python to the system path.
# Download the script to any directory
# Run python get-cloudify.py -f


import sys
import subprocess
import argparse
import platform
import os
import urllib
import struct
import tempfile
import logging
import time
import shutil


DESCRIPTION = '''This script attempts(!) to install Cloudify's CLI on Linux,
Windows (with Python32 AND 64), and OS X (Darwin).
On the linux front, it supports Debian/Ubuntu, CentOS/RHEL and Arch.

Installations are supported for both system python, the currently active
virtualenv and a declared virtualenv (using the --virtualenv flag).

If you're already running the script from within a virtualenv and you're not
providing a --virtualenv path, Cloudify will be installed within the virtualenv
you're in.

Passing the --wheelspath allows for an offline installation of Cloudify
from predownloaded Cloudify dependency wheels. Note that if wheels are found
within the default wheels directory or within --wheelspath, they will (unless
the --forceonline flag is set) be used instead of performing an online
installation.

The script will attempt to install all necessary requirements including
python-dev and gcc (for Fabric on Linux), pycrypto (for Fabric on Windows),
pip and virtualenv depending on the OS and Distro you're running on.
Note that to install certain dependencies (like pip or pythondev), you must
run the script as sudo.

It's important to note that even if you're running as sudo, if you're
installing in a declared virtualenv, the script will drop the root privileges
since you probably declared a virtualenv so that it can be installed using
the current user.
Also note, that if you're running with sudo and you have an active virtualenv,
much like any other python script, the installation will occur in the system
python.

A --nodrop flag can be supplied (If not on Windows) so that you can choose
to not drop root privileges at all.

By default, the script assumes that the Python executable is in the
path and is called 'Python' on Linux and 'c:\python27\python.exe on Windows.
The Python path can be overriden by using the --pythonpath flag.

Please refer to Cloudify's documentation at http://getcloudify.org for
additional information.'''

OS = 'linux'
IS_VIRTUALENV = False
DISTRO = ''
IS_PYX32 = False
ENV_BIN_RELATIVE_PATH = ''
# TODO: put these in a private storage
PIP_URL = 'https://bootstrap.pypa.io/get-pip.py'
PYCR64_URL = 'http://www.voidspace.org.uk/downloads/pycrypto26/pycrypto-2.6.win-amd64-py2.7.exe'  # NOQA
PYCR32_URL = 'http://www.voidspace.org.uk/downloads/pycrypto26/pycrypto-2.6.win32-py2.7.exe'  # NOQA


def init_logger(logger_name):
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                      '[%(name)s] %(message)s',
                                  datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def run(cmd):
    """Executes a command
    """
    lgr.debug('Executing: {0}...'.format(cmd))
    pipe = subprocess.PIPE
    proc = subprocess.Popen(
        cmd, shell=True, stdout=pipe, stderr=pipe)
    proc.aggr_stdout = ''
    # while the process is still running, print output
    while proc.poll() is None:
        output = proc.stdout.readline()
        proc.aggr_stdout += output
        if len(output) > 0:
            lgr.debug(output)
        time.sleep(0.5)
    output = proc.stdout.readline()
    proc.aggr_stdout += output
    if len(output) > 0:
        lgr.debug(output)
    proc.aggr_stderr = proc.stderr.read()
    if len(proc.aggr_stderr) > 0:
        lgr.error(proc.aggr_stderr)
    return proc


def is_root():
    """Check if running as root
    """
    return os.getuid() == 0


def drop_root_privileges():
    """Drop root privileges

    This is used so that when installing cloudify within a virtualenv
    using sudo, the default behavior will not be to install using sudo
    as a virtualenv is created especially so that users don't have to
    install in the system Python or using a Sudoer.
    """
    # maybe we're not root
    if not is_root():
        return

    lgr.info('Dropping root permissions...')
    os.setegid(int(os.environ.get('SUDO_GID', 0)))
    os.seteuid(int(os.environ.get('SUDO_UID', 0)))


def make_virtualenv(virtualenv_dir, python_path):
    """This will create a virtualenv. If no `python_path` is supplied,
    will assume that `python` is in path. This default assumption is provided
    with the argument parser.
    """
    lgr.info('Creating Virtualenv {0}...'.format(virtualenv_dir))
    result = run('virtualenv -p {0} {1}'.format(python_path, virtualenv_dir))
    if not result.returncode == 0:
        sys.exit('Could not create virtualenv: {0}'.format(virtualenv_dir))


def install_module(module, version=False, pre=False, virtualenv_path=False,
                   wheelspath=False, upgrade=False):
    """This will install a module.
    Can specify a specific version.
    Can specify a prerelease.
    Can specify a virtualenv to install in.
    Can specify a local wheelspath to use for offline installation.
    In a Windows envrinoment, a virtualenv bin dir would be declared under
    'VIRTUALENV\\scripts\\'.
    """
    lgr.info('Installing {0}...'.format(module))
    if version:
        module = '{0}=={1}'.format(module, version)
    pip_cmd = 'pip install {0}'.format(module)
    if wheelspath:
        pip_cmd = '{0} --use-wheel --no-index --find-links={1}'.format(
            pip_cmd, wheelspath)
    if pre:
        pip_cmd = '{0} --pre'.format(pip_cmd)
    if upgrade:
        pip_cmd = '{0} --upgrade'.format(pip_cmd)
    if virtualenv_path:
        pip_cmd = os.path.join(virtualenv_path, ENV_BIN_RELATIVE_PATH, pip_cmd)
    if IS_VIRTUALENV and not virtualenv_path:
        lgr.info('Installing within current virtualenv: {0}'.format(
            IS_VIRTUALENV))
    # sudo will be used only when not installing into a virtualenv and sudo
    # is enabled
    result = run(pip_cmd)
    if not result.returncode == 0:
        sys.exit('Could not install module: {0}'.format(module))


def download_file(url, destination):
    lgr.info('Downloading {0} to {1}'.format(url, destination))
    final_url = urllib.urlopen(url).geturl()
    if final_url != url:
        lgr.debug('Redirected to {0}'.format(final_url))
    f = urllib.URLopener()
    f.retrieve(final_url, destination)


def get_os_props():
    distro_info = platform.linux_distribution(full_distribution_name=False)
    os = platform.system()
    distro = distro_info[0]
    release = distro_info[2]
    return os, distro, release


class CloudifyInstaller():
    def __init__(self, args):
        self.args = args

    def execute(self):
        """Installation Logic
        --force argument forces installation of all prerequisites.
        If a wheels directory is found, it will be used for offline
        installation unless explicitly prevented using the --forceonline flag.
        If an offline installation fails (for instance, not all wheels were
        found), an online installation process will commence.
        """
        module = self.args.source or 'cloudify'

        if self.args.force or self.args.installpip:
            self.install_pip()

        if self.args.virtualenv and (
                self.args.force or self.args.installvirtualenv):
            self.install_virtualenv()

        # TODO: check if self.args hasattr installpythondev instead.
        if OS == 'linux' and (self.args.force or self.args.installpythondev):
            self.install_pythondev()
        if (IS_VIRTUALENV or self.args.virtualenv) \
                and not OS == 'windows' and not self.args.nodrop:
            # drop root permissions so that installation is done using the
            # current user.
            drop_root_privileges()
        if self.args.virtualenv:
            if not os.path.isfile(os.path.join(
                    self.args.virtualenv, ENV_BIN_RELATIVE_PATH,
                    ('activate.exe' if OS == 'windows' else 'activate'))):
                make_virtualenv(self.args.virtualenv, self.args.pythonpath)
        # TODO: check if self.args hasattr installpycrypto instead.

        if OS == 'windows' and (self.args.force or self.args.installpycrypto):
            self.install_pycrypto(self.args.virtualenv)

        if self.args.forceonline or not os.path.isdir(self.args.wheelspath):
            install_module(module, self.args.version, self.args.pre,
                           self.args.virtualenv)
        elif os.path.isdir(self.args.wheelspath):
            lgr.info('Wheels directory found: "{0}". '
                     'Attemping offline installation...'.format(
                         self.args.wheelspath))
            try:
                install_module(module, pre=True,
                               virtualenv_path=self.args.virtualenv,
                               wheelspath=self.args.wheelspath,
                               upgrade=self.args.upgrade)
            except Exception as ex:
                lgr.warning('Offline installation failed ({0}).'.format(
                    ex.message))
                install_module(module, self.args.version,
                               self.args.pre, self.args.virtualenv,
                               self.args.upgrade)

    def install_virtualenv(self):
        # TODO: use `install_module` function instead.
        lgr.info('Installing virtualenv...')
        result = run('pip install virtualenv')
        if not result.returncode == 0:
            sys.exit('Could not install Virtualenv.')

    def install_pip(self):
        lgr.info('Installing pip...')
        # TODO: check below to see if pip already exists
        # import distutils
        # if not distutils.spawn.find_executable('pip'):
        tempdir = tempfile.mkdtemp()
        get_pip_path = os.path.join(tempdir, 'get-pip.py')
        try:
            download_file(PIP_URL, get_pip_path)
            result = run('{0} {1}'.format(self.args.pythonpath, get_pip_path))
            if not result.returncode == 0:
                sys.exit('Could not install pip')
        except StandardError as e:
            sys.exit('Failed downloading pip from {0}. reason: {1}'.format(
                     PIP_URL, e.message))
        finally:
            lgr.debug('Removing pip installer...')
            shutil.rmtree(tempdir)

    def install_pythondev(self):
        """Installs python-dev and gcc

        This will try to match a command for your distribution.
        """
        lgr.info('Installing python-dev...')
        if DISTRO in ('ubuntu', 'debian'):
            cmd = 'apt-get install -y gcc python-dev'
        elif DISTRO in ('centos', 'redhat'):
            cmd = 'yum -y install gcc python-devel'
        elif os.path.isfile('/etc/arch-release'):
            # Arch doesn't require a python-dev package.
            # It's already supplied with Python.
            cmd = 'pacman -S gcc --noconfirm'
        elif OS == 'darwin':
            lgr.info('python-dev package not required on Darwin.')
            return
        else:
            sys.exit('python-dev package installation not supported '
                     'in current distribution.')
        run(cmd)

    # Windows only
    def install_pycrypto(self, venv):
        """This will install PyCrypto to be used by Fabric.
        PyCrypto isn't compiled with Fabric on Windows by default thus it needs
        to be provided explicitly.
        It will attempt to install the 32 or 64 bit version according to the
        Python version installed.
        """
        lgr.info('Installing PyCrypto {0}bit...'.format(
            '32' if IS_PYX32 else '64'))
        # easy install is used instead of pip as pip doesn't handle windows
        # executables.
        cmd = 'easy_install {0}'.format(PYCR32_URL if IS_PYX32 else PYCR64_URL)
        if venv:
            # why not use join on all 3 parameters? hmm...
            # there was a problem here.
            cmd = os.path.join(venv, ENV_BIN_RELATIVE_PATH, cmd)
            # cmd = '{0}\\{1}'.format(os.path.join(venv, 'scripts'), cmd)
        run(cmd)


def check_cloudify_installed(virtualenv_path=None):
    if virtualenv_path:
        result = run(os.path.join(virtualenv_path, ENV_BIN_RELATIVE_PATH,
                                  'python -c "import cloudify"'))
        if result.returncode == 0:
            return True
        return False
    else:
        try:
            import cloudify  # NOQA
            return True
        except ImportError:
            return False


def parse_args(args=None):
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    default_group = parser.add_mutually_exclusive_group()
    version_group = parser.add_mutually_exclusive_group()
    online_group = parser.add_mutually_exclusive_group()
    default_group.add_argument('-v', '--verbose', action='store_true',
                               help='Verbose level logging to shell.')
    default_group.add_argument('-q', '--quiet', action='store_true',
                               help='Only print errors.')
    parser.add_argument(
        '-f', '--force', action='store_true',
        help='Force install any requirements (USE WITH CARE!).')
    parser.add_argument(
        '-e', '--virtualenv', type=str,
        help='Path to a Virtualenv to install Cloudify in')
    version_group.add_argument(
        '--version', type=str,
        help='Attempt to install a specific version of Cloudify')
    version_group.add_argument(
        '--pre', action='store_true',
        help='Attempt to install the latest Cloudify Milestone')
    version_group.add_argument(
        '-s', '--source', type=str,
        help='Install from the provided URL or local path')
    parser.add_argument(
        '-u', '--upgrade', action='store_true',
        help='Upgrades Cloudify.')
    online_group.add_argument(
        '--forceonline', action='store_true',
        help='Even if wheels are found locally, install from PyPI.')
    online_group.add_argument(
        '--wheelspath', type=str, default='wheelhouse',
        help='Path to wheels (defaults to "<cwd>/wheelhouse").')
    if OS == 'windows':
        parser.add_argument(
            '--pythonpath', type=str, default='c:/python27/python.exe',
            help='Python path to use (defaults to "python").')
    else:
        parser.add_argument(
            '--nodrop', action='store_true',
            help='Do not drop sudo permissions even when installing '
                 'within a virtualenv.')
        parser.add_argument(
            '--pythonpath', type=str, default='python',
            help='Python path to use (defaults to "python").')
    parser.add_argument(
        '--installpip', action='store_true',
        help='Attempt to install pip')
    parser.add_argument(
        '--installvirtualenv', action='store_true',
        help='Attempt to install Virtualenv')
    if OS == 'linux':
        parser.add_argument(
            '--installpythondev', action='store_true',
            help='Attempt to install Python Developers Package')
    elif OS == 'windows':
        parser.add_argument(
            '--installpycrypto', action='store_true',
            help='Attempt to install PyCrypto')
    return parser.parse_args(args)


def main():
    global OS, DISTRO, RELEASE, IS_VIRTUALENV, \
        IS_PYX32, ENV_BIN_RELATIVE_PATH, args
    os_props = get_os_props()
    OS = os_props[0].lower() if os_props[0] else 'Unknown'
    DISTRO = os_props[1].lower() if os_props[1] else 'Unknown'
    RELEASE = os_props[2].lower() if os_props[2] else 'Unknown'
    if OS not in ('windows', 'linux', 'darwin'):
        sys.exit('OS {0} not supported.'.format(OS))
    args = parse_args()

    if args.quiet:
        lgr.setLevel(logging.ERROR)
    elif args.verbose:
        lgr.setLevel(logging.DEBUG)
    else:
        lgr.setLevel(logging.INFO)

    lgr.debug('Identified OS: {0}'.format(OS))
    lgr.debug('Identified Distribution: {0}'.format(DISTRO))
    lgr.debug('Identified Release: {0}'.format(RELEASE))
    # are we running within a virtualenv? This will potentially affect the
    # destination installation directory
    IS_VIRTUALENV = os.environ.get('VIRTUAL_ENV')
    # check 32/64bit to choose the correct PyCrypto installation (windows only)
    IS_PYX32 = True if struct.calcsize("P") == 4 else False
    # need to check if os.path.join works as expected on windows when
    # declaring these as it seems to provide some problems.
    ENV_BIN_RELATIVE_PATH = 'scripts' if OS == 'windows' else 'bin'

    if check_cloudify_installed(args.virtualenv):
        lgr.info('Cloudify is already installed in the path.')
        if args.upgrade:
            lgr.info('Upgrading...')
        else:
            lgr.error('Use the --upgrade flag to upgrade.')
            sys.exit(1)
    else:
        if args.upgrade:
            lgr.error('Cloudify is not installed. '
                      'Remove the --upgrade flag and try again.')
            sys.exit(1)
    installer = CloudifyInstaller(args)
    installer.execute()
    if args.virtualenv:
        activate_path = os.path.join(
            args.virtualenv, ENV_BIN_RELATIVE_PATH, 'activate')
        if OS == 'windows':
            lgr.info('You can now run: "{0}.bat" to activate '
                     'the Virtualenv.'.format(activate_path))
        else:
            lgr.info('You can now run: "source {0}" to activate '
                     'the Virtualenv.'.format(activate_path))

lgr = init_logger(__file__)


if __name__ == '__main__':
    main()
