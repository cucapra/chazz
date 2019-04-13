import boto3
import enum

# HammerBlade AMI IDs we have available, sorted by priority, with the
# "best" image first.
HB_AMI_IDS = ['ami-0ce51e94bbeba2650', 'ami-0c7ccefee8f931530']


class State(enum.IntEnum):
    """The EC2 instance state codes.
    """
    PENDING = 0
    RUNNING = 16
    SHUTTING_DOWN = 32
    TERMINATED = 48
    STOPPING = 64
    STOPPED = 80


def get_instances(ec2):
    """Generate all the currently available EC2 instances.
    """
    r = ec2.describe_instances()
    for res in r['Reservations']:
        for inst in res['Instances']:
            yield inst


def get_hb_instance(ec2):
    """Return an existing HammerBlade EC2 instance, if one exists.
    Otherwise, return None.
    """
    for inst in get_instances(ec2):
        if inst['ImageId'] in HB_AMI_IDS:
            return inst
    return None


def get_running_instance(ec2):
    """Get a *running* HammerBlade EC2 instance, starting a new one or
    booting up an old one if necessary.
    """
    inst = get_hb_instance(ec2)
    if inst:
        print('found existing instance {}'.format(inst['InstanceId']))
        if inst['State']['Code'] == State.RUNNING:
            return inst
        elif inst['State']['Code'] == State.STOPPED:
            raise NotImplementedError("start the instance")
    else:
        print('no existing instance')
        raise NotImplementedError("should launch a new instance here")


def iron():
    ec2 = boto3.client('ec2')
    inst = get_running_instance(ec2)
    print(inst)


if __name__ == '__main__':
    iron()
