"""Utilities for running HammerBlade in F1.
"""

import boto3
import enum
import shlex
import click
import subprocess
import socket
import time

__version__ = '1.0.0'

# HammerBlade AMI IDs we have available, sorted by priority, with the
# "best" image first.
HB_AMI_IDS = ['ami-0ce51e94bbeba2650', 'ami-0c7ccefee8f931530']

# The user and path to the private key file to use for SSH.
KEY_FILE = 'ironcheese.pem'
USER = 'centos'
SSH_PORT = 22

# The command to run to load the FPGA configuration.
FPGA_LOAD_CMD = 'sudo fpga-load-local-image -S 0 -F -I $AGFI'


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


def test_connect(host, port):
    """Try connecting to `host` on `port`. Return a bool indicating
    whether the connection was successful, i.e., someone is listening on
    that port.
    """
    try:
        sock = socket.create_connection((host, port))
    except ConnectionRefusedError:
        return False
    else:
        sock.close()
        return True


def host_wait(host, port, interval=10):
    """Wait until `host` starts accepting connections on `port` by
    attempting to connect every `interval` seconds.
    """
    while not test_connect(host, port):
        print('{} not yet up on port {}'.format(host, port))
        time.sleep(interval)


def get_instances(ec2):
    """Generate all the currently available EC2 instances.
    """
    r = ec2.describe_instances()
    for res in r['Reservations']:
        for inst in res['Instances']:
            yield inst


def get_hb_instances(ec2):
    """Generate the current EC2 instances based on any of the
    HammerBlade AMIs.
    """
    for inst in get_instances(ec2):
        if inst['ImageId'] in HB_AMI_IDS:
            yield inst


def get_instance(ec2, instance_id):
    """Look up an EC2 instance by its id.
    """
    r = ec2.describe_instances(InstanceIds=[instance_id])
    return r['Reservations'][0]['Instances'][0]


def get_hb_instance(ec2):
    """Return *some* existing HammerBlade EC2 instance, if one exists.
    Otherwise, return None.
    """
    for inst in get_hb_instances(ec2):
        return inst
    return None


def instance_wait(ec2, instance_id, until='instance_running'):
    """Wait for an EC2 instance to transition into a given state.

    Possibilities for `until` include `'instance_running'` and
    `'instance_stopped'`.
    """
    waiter = ec2.get_waiter(until)
    waiter.wait(InstanceIds=[instance_id])


def get_running_instance(ec2):
    """Get a *running* HammerBlade EC2 instance, starting a new one or
    booting up an old one if necessary.
    """
    inst = get_hb_instance(ec2)

    if inst:
        iid = inst['InstanceId']
        print('found existing instance {}'.format(iid))

        if inst['State']['Code'] == State.RUNNING:
            return inst

        elif inst['State']['Code'] == State.STOPPED:
            print('instance is stopped; starting')
            ec2.start_instances(InstanceIds=[iid])

            print('waiting for instance to start')
            instance_wait(ec2, iid)

            # "Refresh" the instance so we have its hostname.
            return get_instance(ec2, iid)

        else:
            raise NotImplementedError(
                "instance in unhandled state: {}".format(inst['State']['Name'])
            )

    else:
        print('no existing instance')
        raise NotImplementedError("should launch a new instance here")


def ssh_command(host):
    """Construct a command for SSHing into an EC2 instance.
    """
    return [
        'ssh',
        '-i', KEY_FILE,
        '{}@{}'.format(USER, host),
    ]


@click.group()
def chazz():
    """Run HammerBlade on F1."""


@chazz.command()
def ssh():
    """Connect to a HammerBlade instance with SSH.
    """
    ec2 = boto3.client('ec2')
    inst = get_running_instance(ec2)
    host = inst['PublicDnsName']

    # Wait for the host to start its SSH server.
    host_wait(host, SSH_PORT)

    # Run the FPGA configuration command via SSH.
    cmd = ssh_command(host)
    load_cmd = cmd + [FPGA_LOAD_CMD]
    print(fmt_cmd(load_cmd))
    subprocess.run(load_cmd)

    # Run the interactive SSH command.
    print(fmt_cmd(cmd))
    subprocess.run(cmd)


@chazz.command()
def list():
    """Show the available HammerBlade instances.
    """
    ec2 = boto3.client('ec2')
    for inst in get_hb_instances(ec2):
        print('{0[InstanceId]} ({0[State][Name]}): {0[ImageId]}'.format(inst))


@chazz.command()
@click.option('--wait/--no-wait', default=False,
              help='Wait for the instances to stop.')
def stop(wait):
    """Stop all running HammerBlade instances.
    """
    ec2 = boto3.client('ec2')
    for inst in get_hb_instances(ec2):
        if inst['State']['Code'] == State.RUNNING:
            iid = inst['InstanceId']

            print('stopping {}'.format(iid))
            ec2.stop_instances(InstanceIds=[iid])

            if wait:
                instance_wait(ec2, iid, 'instance_stopped')


if __name__ == '__main__':
    chazz()
