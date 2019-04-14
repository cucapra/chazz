import boto3
import enum
import shlex
import click

# HammerBlade AMI IDs we have available, sorted by priority, with the
# "best" image first.
HB_AMI_IDS = ['ami-0ce51e94bbeba2650', 'ami-0c7ccefee8f931530']

# The user and path to the private key file to use for SSH.
KEY_FILE = 'ironcheese.pem'
USER = 'centos'


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


def get_hb_instance(ec2):
    """Return *some* existing HammerBlade EC2 instance, if one exists.
    Otherwise, return None.
    """
    for inst in get_hb_instances(ec2):
        return inst
    return None


def wait_for_instance(ec2, instance_id):
    """Wait for an EC2 instance to transition into running state.
    """
    waiter = ec2.get_waiter('instance_running')
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
            r = ec2.start_instances(InstanceIds=[iid])
            print(r)

            print('waiting for instance to start')
            wait_for_instance(iid)

            return inst

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
    print(fmt_cmd(ssh_command(inst['PublicDnsName'])))


@chazz.command()
def list():
    """Show the available HammerBlade instances.
    """
    ec2 = boto3.client('ec2')
    for inst in get_hb_instances(ec2):
        print('{0[InstanceId]} ({0[State][Name]}): {0[ImageId]}'.format(inst))


if __name__ == '__main__':
    chazz()
