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

__version__ = '1.0.0'

# HammerBlade AMIs we have available. Map version names to AMI IDs.
HB_AMI_IDS = {
    'v0.4.2':   'ami-0ebfadb08765d6ddf',
    '20190511': 'ami-0e1d91c72cabb5b3f',
    '20190510': 'ami-0343798c9b9136e4e',
    '20190417': 'ami-0270f06e16bfee050',
    '20190405': 'ami-0ce51e94bbeba2650',
    '20190319': 'ami-0c7ccefee8f931530',
}
HB_AMI_DEFAULT = 'v0.4.2'

# Some AWS parameters.
AWS_REGION = 'us-west-2'  # The Oregon region.
EC2_TYPE = 'f1.2xlarge'  # Launch the smallest kind of F1 instance.

# The path to the private key file to use for SSH. We use the
# environment variable if it's set and this filename otherwise.
KEY_ENVVAR = 'CHAZZ_KEY'
KEY_FILE = 'ironcheese.pem'

# User and port for SSH.
USER = 'centos'
SSH_PORT = 22

# The setup script to run on new images.
SETUP_SCRIPT = os.path.join(os.path.dirname(__file__), 'setup.sh')


# Logger.
log = logging.getLogger(__name__)
click_log.basic_config(log)


# Configuration object.
Config = namedtuple("Config", [
    'ec2',  # Boto EC2 client object.
    'ami_ids',  # Mapping from version names to AMI IDs.
    'ami_default',  # Name of the default version to use.
    'ssh_key',  # Path to the SSH private key file.
    'key_name',  # The EC2 keypair name.
    'security_group',  # AWS security group (which must allow SSH).
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


def get_instances(ec2):
    """Generate all the currently available EC2 instances.
    """
    r = ec2.describe_instances()
    for res in r['Reservations']:
        for inst in res['Instances']:
            yield inst


def get_hb_instances(config):
    """Generate the current EC2 instances based on any of the
    HammerBlade AMIs.
    """
    for inst in get_instances(config.ec2):
        if inst['ImageId'] in config.ami_ids.values():
            yield inst


def get_instance(ec2, instance_id):
    """Look up an EC2 instance by its id.
    """
    r = ec2.describe_instances(InstanceIds=[instance_id])
    return r['Reservations'][0]['Instances'][0]


def get_hb_instance(config):
    """Return *some* existing HammerBlade EC2 instance for the *default*
    image, if one exists. Otherwise, return None.
    """
    for inst in get_hb_instances(config):
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
    """Create (and start) a new HammerBlade EC2 instance.
    """
    res = config.ec2.run_instances(
        ImageId=config.ami_ids[config.ami_default],
        InstanceType=EC2_TYPE,
        MinCount=1,
        MaxCount=1,
        KeyName=config.key_name,
        SecurityGroups=[config.security_group],
    )
    assert len(res['Instances']) == 1
    return res['Instances'][0]


def get_running_instance(config):
    """Get a *running* HammerBlade EC2 instance, starting a new one or
    booting up an old one if necessary.
    """
    inst = get_hb_instance(config)

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


def _ssh_host(host):
    """Get the full user/host pair for use in SSH commands."""
    return '{}@{}'.format(USER, host)


def ssh_command(config, host):
    """Construct a command for SSHing into an EC2 instance.
    """
    return [
        'ssh',
        '-i', config.ssh_key,
        _ssh_host(host),
    ]


def run_setup(config, host):
    """Set up the host by copying our setup script and running it.
    """
    log.info('running setup script')

    # Read the setup script.
    with open(SETUP_SCRIPT, 'rb') as f:
        setup_script = f.read()

    # Pipe the command into sh on the host.
    sh_cmd = ssh_command(config, host) + ['sh']
    log.debug(fmt_cmd(sh_cmd))
    subprocess.run(sh_cmd, input=setup_script)


def fmt_inst(config, inst):
    """Format an EC2 instance object as a string for display.
    """
    ami_names = {v: k for (k, v) in config.ami_ids.items()}
    return '{0[InstanceId]} ({0[State][Name]}): {1}'.format(
        inst,
        ami_names.get(inst['ImageId'], inst['ImageId']),
    )


@click.group()
@click.pass_context
@click.option('--ami', default=None,
              help='An AMI ID for HammerBlade images.')
@click.option('-i', '--image', default=HB_AMI_DEFAULT,
              help='Version name for the image to use for new instances.')
@click.option('--key-pair', metavar='NAME', default='ironcheese',
              help='Name of the AWS key pair to add to new instances.')
@click.option('--security-group', metavar='NAME', default='chazz',
              help='An AWS security group that allows SSH.')
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Include debug output.')
def chazz(ctx, verbose, ami, image, key_pair, security_group):
    """Run HammerBlade on F1."""
    if verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    ami_ids = dict(HB_AMI_IDS)
    if ami:
        ami_ids['cli'] = ami
        image = 'cli'
    elif image not in ami_ids:
        ctx.fail('image must be one of {}'.format(', '.join(ami_ids)))

    ctx.obj = Config(
        ec2=boto3.client('ec2', region_name=AWS_REGION),
        ami_ids=ami_ids,
        ami_default=image,
        ssh_key=os.environ.get(KEY_ENVVAR, KEY_FILE),
        key_name=key_pair,
        security_group=security_group,
    )
    log.debug('%s', ctx.obj)


@chazz.command()
@click.pass_obj
def ssh(config):
    """Connect to a HammerBlade instance with SSH.
    """
    inst = get_running_instance(config)
    host = inst['PublicDnsName']

    # Wait for the host to start its SSH server.
    host_wait(host, SSH_PORT)

    # Set up the VM.
    run_setup(config, host)

    # Run the interactive SSH command.
    cmd = ssh_command(config, host)
    log.info(fmt_cmd(cmd))
    subprocess.run(cmd)


@chazz.command()
@click.pass_obj
@click.argument('cmd', required=False, default='exec "$SHELL"')
def shell(config, cmd):
    """Launch a shell for convenient SSH invocation.
    """
    inst = get_running_instance(config)
    host = inst['PublicDnsName']

    cmd = [
        'ssh-agent', 'sh', '-c',
        'ssh-add "$HB_KEY" ; {}'.format(cmd),
    ]
    subprocess.run(cmd, env={
        'HB': _ssh_host(host),
        'HB_HOST': host,
        'HB_KEY': os.path.abspath(config.ssh_key),
    })


@chazz.command()
@click.pass_obj
def start(config):
    """Ensure that a HammerBlade instance is running.
    """
    inst = get_running_instance(config)
    print(fmt_inst(config, inst))


@chazz.command()
@click.pass_obj
def list(config):
    """Show the available HammerBlade instances.
    """
    for inst in get_hb_instances(config):
        print(fmt_inst(config, inst))


@chazz.command()
@click.pass_obj
@click.option('--wait/--no-wait', default=False,
              help='Wait for the instances to stop.')
@click.option('--terminate/--stop', default=False,
              help='Destroy the instance, or just stop it (the default).')
def stop(config, wait, terminate):
    """Stop all running HammerBlade instances.
    """
    for inst in get_hb_instances(config):
        iid = inst['InstanceId']
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
@click.option('--watch', '-w', is_flag=True, default=False,
              help='Use entr to wait for changes and automatically sync.')
def sync(config, src, dest, watch):
    """Synchronize files with an instance.
    """
    # Get a connectable host.
    inst = get_running_instance(config)
    host = inst['PublicDnsName']
    host_wait(host, SSH_PORT)

    # Concoct the rsync command.
    rsync_cmd = [
        'rsync', '--checksum', '--itemize-changes', '--recursive',
        '-e', 'ssh -i {}'.format(shlex.quote(config.ssh_key)),
        src, '{}:{}'.format(_ssh_host(host), dest),
    ]

    if watch:
        # Use entr(1) to watch for changes.
        find_cmd = ['find', src]
        entr_cmd = ['entr'] + rsync_cmd
        log.info('{} | {}'.format(fmt_cmd(find_cmd), fmt_cmd(entr_cmd)))

        find_proc = subprocess.Popen(find_cmd, stdout=subprocess.PIPE)
        entr_proc = subprocess.Popen(entr_cmd, stdin=find_proc.stdout)
        find_proc.stdout.close()
        entr_proc.wait()

    else:
        # Just rsync once.
        log.info(fmt_cmd(rsync_cmd))
        subprocess.run(rsync_cmd)


if __name__ == '__main__':
    chazz()
