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

__version__ = '1.0.0'

# HammerBlade AMI IDs we have available. Put the "best" image first:
# this is the one we'll use to start new instances.
HB_AMI_IDS = [
    'ami-0ebfadb08765d6ddf',  # v0.4.2
    'ami-0e1d91c72cabb5b3f',  # 20190511
    'ami-0343798c9b9136e4e',  # 20190510
    'ami-0270f06e16bfee050',  # 20190417
    'ami-0ce51e94bbeba2650',  # 20190405 (target for our example)
    'ami-0c7ccefee8f931530',  # 20190319
]

# Some AWS parameters.
AWS_REGION = 'us-west-2'  # The Oregon region.
EC2_TYPE = 'f1.2xlarge'  # Launch the smallest kind of F1 instance.
KEY_NAME = 'ironcheese'  # The name of the EC2 keypair.
SECURITY_GROUP = 'chazz'  # The name of a security group that allows SSH.

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


def get_hb_instances(ec2, ami_ids):
    """Generate the current EC2 instances based on any of the
    HammerBlade AMIs.
    """
    for inst in get_instances(ec2):
        if inst['ImageId'] in ami_ids:
            yield inst


def get_instance(ec2, instance_id):
    """Look up an EC2 instance by its id.
    """
    r = ec2.describe_instances(InstanceIds=[instance_id])
    return r['Reservations'][0]['Instances'][0]


def get_hb_instance(ec2, ami_ids):
    """Return *some* existing HammerBlade EC2 instance, if one exists.
    Otherwise, return None.
    """
    for inst in get_hb_instances(ec2, ami_ids):
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


def create_instance(ec2, ami_ids):
    """Create (and start) a new HammerBlade EC2 instance.
    """
    res = ec2.run_instances(
        ImageId=ami_ids[0],
        InstanceType=EC2_TYPE,
        MinCount=1,
        MaxCount=1,
        KeyName=KEY_NAME,
        SecurityGroups=[SECURITY_GROUP],
    )
    assert len(res['Instances']) == 1
    return res['Instances'][0]


def get_running_instance(ec2, ami_ids):
    """Get a *running* HammerBlade EC2 instance, starting a new one or
    booting up an old one if necessary.
    """
    inst = get_hb_instance(ec2, ami_ids)

    if inst:
        iid = inst['InstanceId']
        log.info('found existing instance {}'.format(iid))

        if inst['State']['Code'] == State.RUNNING:
            return inst

        elif inst['State']['Code'] == State.STOPPED:
            log.info('instance is stopped; starting')
            ec2.start_instances(InstanceIds=[iid])

            log.info('waiting for instance to start')
            instance_wait(ec2, iid)

            # "Refresh" the instance so we have its hostname.
            return get_instance(ec2, iid)

        else:
            raise NotImplementedError(
                "instance in unhandled state: {}".format(inst['State']['Name'])
            )

    else:
        log.info('no existing instance; creating a new one')
        inst = create_instance(ec2, ami_ids)

        log.info('waiting for new instance to start')
        instance_wait(ec2, inst['InstanceId'])

        return get_instance(ec2, inst['InstanceId'])


def _ssh_key():
    """Get the path to the SSH key file."""
    return os.environ.get(KEY_ENVVAR, KEY_FILE)


def _ssh_host(host):
    """Get the full user/host pair for use in SSH commands."""
    return '{}@{}'.format(USER, host)


def ssh_command(host):
    """Construct a command for SSHing into an EC2 instance.
    """
    return [
        'ssh',
        '-i', _ssh_key(),
        _ssh_host(host),
    ]


def scp_command(src, host, dest):
    """Construct an scp command for copying a local file to a remote
    host.
    """
    return [
        'scp',
        '-i', _ssh_key(),
        src,
        '{}:{}'.format(_ssh_host(host), dest),
    ]


def run_setup(host):
    """Set up the host by copying our setup script and running it.
    """
    log.info('running setup script')

    # Read the setup script.
    with open(SETUP_SCRIPT, 'rb') as f:
        setup_script = f.read()

    # Pipe the command into sh on the host.
    sh_cmd = ssh_command(host) + ['sh']
    log.debug(fmt_cmd(sh_cmd))
    subprocess.run(sh_cmd, input=setup_script)


def _fmt_inst(inst):
    """Format an EC2 instance object as a string for display.
    """
    return '{0[InstanceId]} ({0[State][Name]}): {0[ImageId]}'.format(inst)


@click.group()
@click.pass_context
@click.option('--ami', multiple=True, default=HB_AMI_IDS,
              help='An AMI ID for HammerBlade images.')
@click.option('-i', '--image', multiple=True, type=int,
              help='An image index to use (exclusively).')
@click_log.simple_verbosity_option(log)
def chazz(ctx, ami, image):
    """Run HammerBlade on F1."""
    ctx.ensure_object(dict)
    ctx.obj['EC2'] = boto3.client('ec2', region_name=AWS_REGION)
    if image:
        ctx.obj['AMI_IDS'] = [HB_AMI_IDS[i] for i in image]
    else:
        ctx.obj['AMI_IDS'] = ami


@chazz.command()
@click.pass_context
def ssh(ctx):
    """Connect to a HammerBlade instance with SSH.
    """
    ec2 = ctx.obj['EC2']

    inst = get_running_instance(ec2, ctx.obj['AMI_IDS'])
    host = inst['PublicDnsName']

    # Wait for the host to start its SSH server.
    host_wait(host, SSH_PORT)

    # Set up the VM.
    run_setup(host)

    # Run the interactive SSH command.
    cmd = ssh_command(host)
    log.info(fmt_cmd(cmd))
    subprocess.run(cmd)


@chazz.command()
@click.pass_context
@click.argument('cmd', required=False, default='exec "$SHELL"')
def shell(ctx, cmd):
    """Launch a shell for convenient SSH invocation.
    """
    ec2 = ctx.obj['EC2']

    inst = get_running_instance(ec2, ctx.obj['AMI_IDS'])
    host = inst['PublicDnsName']

    cmd = [
        'ssh-agent', 'sh', '-c',
        'ssh-add "$HB_KEY" ; {}'.format(cmd),
    ]
    subprocess.run(cmd, env={
        'HB': _ssh_host(host),
        'HB_HOST': host,
        'HB_KEY': os.path.abspath(_ssh_key()),
    })


@chazz.command()
@click.pass_context
def start(ctx):
    """Ensure that a HammerBlade instance is running.
    """
    ec2 = ctx.obj['EC2']
    inst = get_running_instance(ec2, ctx.obj['AMI_IDS'])
    print(_fmt_inst(inst))


@chazz.command()
@click.pass_context
def list(ctx):
    """Show the available HammerBlade instances.
    """
    ec2 = ctx.obj['EC2']
    for inst in get_hb_instances(ec2, ctx.obj['AMI_IDS']):
        print(_fmt_inst(inst))


@chazz.command()
@click.pass_context
@click.option('--wait/--no-wait', default=False,
              help='Wait for the instances to stop.')
@click.option('--terminate/--stop', default=False,
              help='Destroy the instance, or just stop it (the default).')
def stop(ctx, wait, terminate):
    """Stop all running HammerBlade instances.
    """
    ec2 = ctx.obj['EC2']
    for inst in get_hb_instances(ec2, ctx.obj['AMI_IDS']):
        iid = inst['InstanceId']
        if terminate:
            if inst['State']['Code'] != State.TERMINATED:
                log.info('terminating {}'.format(iid))
                ec2.terminate_instances(InstanceIds=[iid])
                if wait:
                    instance_wait(ec2, iid, 'instance_terminated')
        else:
            if inst['State']['Code'] == State.RUNNING:
                log.info('stopping {}'.format(iid))
                ec2.stop_instances(InstanceIds=[iid])
                if wait:
                    instance_wait(ec2, iid, 'instance_stopped')


@chazz.command()
@click.pass_context
@click.argument('src', type=click.Path(exists=True))
@click.argument('dest', required=False, default='')
def sync(ctx, src, dest):
    """Synchronize files with an instance.
    """
    ec2 = ctx.obj['EC2']

    # Get a connectable host.
    inst = get_running_instance(ec2, ctx.obj['AMI_IDS'])
    host = inst['PublicDnsName']
    host_wait(host, SSH_PORT)

    # Concoct the rsync command.
    rsync_cmd = [
        'rsync', '--checksum', '--itemize-changes', '--recursive',
        '-e', 'ssh -i {}'.format(shlex.quote(_ssh_key())),
        src, '{}:{}'.format(_ssh_host(host), dest),
    ]

    # Run the command.
    log.info(fmt_cmd(rsync_cmd))
    subprocess.run(rsync_cmd)


if __name__ == '__main__':
    chazz()
