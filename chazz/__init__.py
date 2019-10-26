"""Utilities for running HammerBlade in F1.
"""

import boto3
import enum
import shlex
import click
import subprocess
import socket
import time
import os
import logging
import click_log
from collections import namedtuple
import tomlkit

__version__ = '1.0.0'

SSH_PORT = 22

# The setup script to run on new images.
SETUP_SCRIPT = os.path.join(os.path.dirname(__file__), 'setup.sh')

# Paths for the user configuration and the configuration defaults.
CONFIG_PATH = os.path.expanduser('~/.config/chazz.toml')
DEFAULT_PATH = os.path.join(os.path.dirname(__file__), 'config_default.toml')


# Logger.
log = logging.getLogger(__name__)
click_log.basic_config(log)


# Configuration object.
Config = namedtuple("Config", [
    'ec2',  # Boto EC2 client object.
    'ami_ids',  # Mapping from version names to AMI IDs.
    'ami_default',  # Name of the image to boot, or None to disable creation.
    'ssh_key',  # Path to the SSH private key file.
    'key_name',  # The EC2 keypair name.
    'security_group',  # AWS security group (which must allow SSH).
    'ec2_type',  # EC2 instance type to create.
    'user',  # SSH username.
    'scripts',  # Scripts for `run`, and a special `setup` script.
])


class State(enum.IntEnum):
    """The EC2 instance state codes.
    """
    PENDING = 0
    RUNNING = 16
    SHUTTING_DOWN = 32
    TERMINATED = 48
    STOPPING = 64
    STOPPED = 80


def fmt_cmd(cmd):
    """Format a shell command, given as a list of arguments a single
    copy-n-pastable string.
    """
    return ' '.join(shlex.quote(s) for s in cmd)


def test_connect(host, port, timeout=2):
    """Try connecting to `host` on `port`. Return a bool indicating
    whether the connection was successful, i.e., someone is listening on
    that port.
    """
    try:
        sock = socket.create_connection((host, port), timeout)
    except ConnectionRefusedError:
        log.debug('connection refused')
        return False
    except socket.timeout:
        log.debug('connection timeout')
        return False
    else:
        sock.close()
        return True


def host_wait(host, port, interval=10):
    """Wait until `host` starts accepting connections on `port` by
    attempting to connect every `interval` seconds.
    """
    while not test_connect(host, port):
        log.debug('{} not yet up on port {}'.format(host, port))
        time.sleep(interval)


def all_instances(ec2):
    """Generate all the currently available EC2 instances.
    """
    r = ec2.describe_instances()
    for res in r['Reservations']:
        for inst in res['Instances']:
            yield inst


def get_instances(config):
    """Generate the current EC2 instances that are either based on any
    of the configured AMIs or have matadata names.
    """
    for inst in all_instances(config.ec2):
        if inst['ImageId'] in config.ami_ids.values() or \
                get_instance_name(inst):
            yield inst


def get_instance_name(inst):
    """Get the name of an instance, or None if it doesn't have one.

    The name is the value for the metadata tag "Name," if it exists.
    """
    if inst.get('Tags'):
        for tag in inst['Tags']:
            if tag['Key'] == 'Name':
                return tag['Value']
    return None


def get_instance(ec2, instance_id):
    """Look up an EC2 instance by its id.
    """
    r = ec2.describe_instances(InstanceIds=[instance_id])
    return r['Reservations'][0]['Instances'][0]


def get_default_instance(config):
    """Return *some* existing EC2 instance for the *default* image, if
    one exists. Otherwise, return None.
    """
    for inst in get_instances(config):
        if inst['ImageId'] != config.ami_ids[config.ami_default]:
            # Only consider the default image.
            continue
        if inst['State']['Code'] in (State.TERMINATED, State.SHUTTING_DOWN):
            # Ignore terminated instances.
            continue
        return inst
    return None


def instance_wait(ec2, instance_id, until='instance_running'):
    """Wait for an EC2 instance to transition into a given state.

    Possibilities for `until` include `'instance_running'` and
    `'instance_stopped'`.
    """
    waiter = ec2.get_waiter(until)
    waiter.wait(InstanceIds=[instance_id])


def create_instance(config):
    """Create (and start) a new EC2 instance using the default AMI.
    """
    if not config.ami_default:
        raise click.UsageError(
            'No default AMI specified. Cannot create instances.'
        )
    res = config.ec2.run_instances(
        ImageId=config.ami_ids[config.ami_default],
        InstanceType=config.ec2_type,
        MinCount=1,
        MaxCount=1,
        KeyName=config.key_name,
        SecurityGroups=[config.security_group],
    )
    assert len(res['Instances']) == 1
    return res['Instances'][0]


def get_named_instance(ec2, name):
    """Get an instance with the metadata name `name`, or None if no such
    named instance exists.
    """
    for inst in all_instances(ec2):
        if get_instance_name(inst) == name:
            return inst
    return None


def get_running_instance(config, name):
    """Get a *running* EC2 instance, starting a new one or booting up an
    old one if necessary.

    If `name` is specified, get the instance with that name, or throw a
    `click.UserError` if it does not exist. Otherwise, look for any
    instance with the default AMI.
    """
    if name:
        inst = get_named_instance(config.ec2, name)
        if not inst:
            raise click.UsageError('Instance {} not found.'.format(name))
    else:
        inst = get_default_instance(config)

    if inst:
        iid = inst['InstanceId']
        log.info('found existing instance {}'.format(iid))

        if inst['State']['Code'] == State.RUNNING:
            return inst

        elif inst['State']['Code'] == State.STOPPED:
            log.info('instance is stopped; starting')
            config.ec2.start_instances(InstanceIds=[iid])

            log.info('waiting for instance to start')
            instance_wait(config.ec2, iid)

            # "Refresh" the instance so we have its hostname.
            return get_instance(config.ec2, iid)

        else:
            raise NotImplementedError(
                "instance in unhandled state: {}".format(inst['State']['Name'])
            )

    else:
        log.info('no existing instance; creating a new one')
        inst = create_instance(config)

        log.info('waiting for new instance to start')
        instance_wait(config.ec2, inst['InstanceId'])

        return get_instance(config.ec2, inst['InstanceId'])


def ssh_host(config, host):
    """Get the full user/host pair for use in SSH commands."""
    return '{}@{}'.format(config.user, host)


def ssh_command(config, host):
    """Construct a command for SSHing into an EC2 instance.
    """
    return [
        'ssh',
        '-i', config.ssh_key,
        '-o', 'StrictHostKeyChecking no',
        ssh_host(config, host),
    ]


def run_script(config, host, scriptname):
    """Run a script from config on host.
    """
    if scriptname not in config.scripts:
        raise click.UsageError('Script "{}" not found.'.format(scriptname))

    log.info('running script {}'.format(scriptname))
    sh_cmd = ssh_command(config, host) + ['sh']
    log.debug(fmt_cmd(sh_cmd))
    subprocess.run(sh_cmd, input=config.scripts[scriptname].encode())


def fmt_inst(config, inst):
    """Format an EC2 instance object as a string for display.
    """
    ami_names = {v: k for (k, v) in config.ami_ids.items()}
    return '{} ({}): {}'.format(
        get_instance_name(inst) or inst['InstanceId'],
        inst['State']['Name'],
        ami_names.get(inst['ImageId'], inst['ImageId']),
    )


def load_config():
    """Load the configuration object by merging the default options with
    the user configuration file.
    """
    with open(DEFAULT_PATH) as f:
        config = tomlkit.loads(f.read())

    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config.update(tomlkit.loads(f.read()))

    return config


@click.group()
@click.pass_context
@click.option('--ami', default=None,
              help='An AMI ID to use for finding and creating instances.')
@click.option('-i', '--image', default=None,
              help='Version name for the image for connection & creation.')
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Include debug output.')
@click.option('--user', '-u', default=None, help='SSH username.')
def chazz(ctx, verbose, ami, image, user):
    """Run HammerBlade on F1."""
    if verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    # Load the configuration from the user's config file & defaults.
    config_opts = load_config()

    # Options to choose specific images. The image (i.e.,
    # `config.ami_default`) is necessary to support instance *creation*;
    # when it's None, we can only interact with existing instances.
    image = image or config_opts['default_ami'] or None
    ami_ids = dict(config_opts['ami_ids'])
    if ami:
        ami_ids['cli'] = ami
        image = 'cli'
    elif image and image not in ami_ids:
        ctx.fail('image must be one of {}; not {}'.format(
            ', '.join(ami_ids),
            image,
        ))

    ec2 = boto3.client('ec2', region_name=config_opts['aws_region'])

    ctx.obj = Config(
        ec2=ec2,
        ami_ids=ami_ids,
        ami_default=image,
        ssh_key=os.path.expanduser(config_opts['ssh_key']),
        key_name=config_opts['key_name'],
        security_group=config_opts['security_group'],
        ec2_type=config_opts['ec2_type'],
        user=user or config_opts['user'],
        scripts=config_opts['scripts'],
    )
    log.debug('%s', ctx.obj)


@chazz.command()
@click.pass_obj
@click.argument('name', required=False, metavar='[INSTANCE]')
@click.argument('scripts', nargs=-1, metavar='[SCRIPTS]')
@click.option('--no-exit', '-N', is_flag=True, default=False,
              help="Don't exit instance after running scripts.")
def run(config, name, scripts, no_exit):
    """Run configured scripts on an instance.

    SCRIPTS are the names of shell scripts from the configuration file.
    Multiple scripts are run in the order specified.
    """
    inst = get_running_instance(config, name)
    host = inst['PublicDnsName']

    # Wait for the host to start its SSH server.
    host_wait(host, SSH_PORT)

    for script in scripts:
        run_script(config, host, script)

    # Run the interactive SSH command.
    if no_exit:
        cmd = ssh_command(config, host)
        log.info(fmt_cmd(cmd))
        subprocess.run(cmd)


@chazz.command()
@click.pass_obj
@click.argument('name', required=False, metavar='[INSTANCE]')
def ssh(config, name):
    """Connect to an instance with SSH.

    INSTANCE may be either an instance ID or a metadata name. Omit it to
    connect to a running instance with the default AMI or launch a new
    one if no instance is running.
    """
    inst = get_running_instance(config, name)
    host = inst['PublicDnsName']

    # Wait for the host to start its SSH server.
    host_wait(host, SSH_PORT)

    # Set up the VM.
    run_script(config, host, 'setup')

    # Run the interactive SSH command.
    cmd = ssh_command(config, host)
    log.info(fmt_cmd(cmd))
    subprocess.run(cmd)


@chazz.command()
@click.pass_obj
@click.argument('name', required=False, metavar='[INSTANCE]')
@click.argument('cmd', required=False, default='exec "$SHELL"')
def shell(config, name, cmd):
    """Launch a shell for convenient SSH invocation.
    """
    inst = get_running_instance(config, name)
    host = inst['PublicDnsName']

    cmd = [
        'ssh-agent', 'sh', '-c',
        'ssh-add "$HB_KEY" ; {}'.format(cmd),
    ]
    subprocess.run(cmd, env={
        **os.environ,
        'HB': ssh_host(config, host),
        'HB_HOST': host,
        'HB_KEY': os.path.abspath(config.ssh_key),
    })


@chazz.command()
@click.pass_obj
@click.argument('name', required=False, metavar='[INSTANCE]')
def start(config, name):
    """Ensure that an instance is running.
    """
    inst = get_running_instance(config, name)
    print(fmt_inst(config, inst))


@chazz.command()
@click.pass_obj
def list(config):
    """Show the available instances.

    The list includes all instances that either use one of the
    configured AMIs or has a metadata tag "Name".
    """
    for inst in get_instances(config):
        print(fmt_inst(config, inst))


@chazz.command()
@click.pass_obj
@click.argument('name', required=False, metavar='[INSTANCE]')
@click.option('--wait/--no-wait', default=False,
              help='Wait for the instances to stop.')
@click.option('--terminate/--stop', default=False,
              help='Destroy the instance, or just stop it (the default).')
def stop(config, name, wait, terminate):
    """Stop all running instances, or one given by its name or ID.
    """
    # If `name` is specified, it can either be a name or an ID.
    stop_id = None
    if name:
        inst = get_named_instance(config.ec2, name)
        if inst:
            stop_id = inst['InstanceId']
        else:
            stop_id = name

    for inst in get_instances(config):
        iid = inst['InstanceId']
        if stop_id and iid != stop_id:
            continue

        if terminate:
            if inst['State']['Code'] != State.TERMINATED:
                log.info('terminating {}'.format(iid))
                config.ec2.terminate_instances(InstanceIds=[iid])
                if wait:
                    instance_wait(config.ec2, iid, 'instance_terminated')
        else:
            if inst['State']['Code'] == State.RUNNING:
                log.info('stopping {}'.format(iid))
                config.ec2.stop_instances(InstanceIds=[iid])
                if wait:
                    instance_wait(config.ec2, iid, 'instance_stopped')


@chazz.command()
@click.pass_obj
@click.argument('src', type=click.Path(exists=True))
@click.argument('dest', required=False, default='')
@click.argument('name', required=False, metavar='[INSTANCE]')
@click.option('--watch', '-w', is_flag=True, default=False,
              help='Use entr to wait for changes and automatically sync.')
def sync(config, src, dest, name, watch):
    """Synchronize files with an instance.
    """
    # Get a connectable host.
    inst = get_running_instance(config, name)
    host = inst['PublicDnsName']
    host_wait(host, SSH_PORT)

    # Concoct the rsync command.
    rsync_cmd = [
        'rsync', '--checksum', '--itemize-changes', '--recursive',
        '--copy-links',
        '-e', 'ssh -i {}'.format(shlex.quote(config.ssh_key)),
        os.path.normpath(src),
        '{}:{}'.format(ssh_host(config, host), os.path.normpath(dest)),
    ]

    if watch:
        # Use `watchexec` to watch for changes.
        we_cmd = ['watchexec', '-w', src, '-n', '--'] + rsync_cmd
        log.info(fmt_cmd(we_cmd))
        subprocess.run(we_cmd)

    else:
        # Just rsync once.
        log.info(fmt_cmd(rsync_cmd))
        subprocess.run(rsync_cmd)


if __name__ == '__main__':
    chazz()
