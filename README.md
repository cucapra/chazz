Chazz: A Tool for Running HammerBlade in F1
===========================================

This is a little utility for interacting with HammerBlade machines running in [F1][].
It's another [*Blades of Glory*][bog] reference.

[f1]: https://aws.amazon.com/ec2/instance-types/f1/
[bog]: https://www.imdb.com/title/tt0445934/


Install
-------

This tool is written for Python 3.
We will need [Flit][] to install it:

    $ pip install --user flit

Then, install the program itself:

    $ flit install --symlink --user

The `--symlink` flag means that you can edit the code and use it immediately.

[flit]: https://flit.readthedocs.io/en/latest/


Set Up
------

First, set up your [AWS configuration][config].
You can type `aws configure` (if you have the AWS CLI) or manually create the files.
On a shared account, you may need to create yourself an [IAM user][iam] with "programmatic access" to get an access key.
You don't need to configure a default region; Chazz specifies the region itself.

Next, obtain the private key.
Make sure the permissions are right:

    $ chmod 0600 ironcheese.pem

You can either use that name or create a configuration file at `~/.config/chazz.toml` to point to the key file:

    ssh_key = "~/chazz/ironcheese.pem"

[config]: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#configuration
[iam]: https://console.aws.amazon.com/iam/home?#/users


Use
---

Type `chazz` to see a list of available commands.

### Start and Connect to Instances

To boot up an instance and SSH into it, type `chazz ssh`.
Before giving you a prompt, the tool runs a command to load the FPGA configuration.
Use the instance like normal, then disconnect.
Type `chazz stop` to stop the instance (and stop paying for it).
Or use `chazz stop --terminate` to permanently decommission the instance.
The command stops _all_ instances by default; to stop just one, give its instance ID.

You can see a list of available HammerBlade instances with `chazz list`.
There is also a `chazz start` command, which is like `chazz ssh` in that it ensures that there's a running instance, but it does not *also* attempt to connect with SSH.

### Transfer Files (Automatically)

It can get a little annoying to edit files on the VM, so Chazz can help synchronize files you edit locally.
Type `chazz sync foo` to [rsync][] `foo` to the server.
The `-w` flag uses [watchexec][] to watch for changes to files and automatically send them to the server.
The `--down` flag downloads file instead of uploading them.

### Get a Shell for Typing Arbitrary SSH Commands

For more complex interactions with a HammerBlade server, use `chazz shell`.
You get an interactive shell with the appropriate key pre-loaded in an SSH agent and the host in an environment variable called `$HB`.
So you can type `ssh $HB` to connect or `scp -r hb-examples $HB:` to upload files.
Or to run a specific command, pass it as an argument, as in `chazz shell 'scp something.c $HB:'`.

### Configuration

The [TOML][] configuration file is at `~/.config/chazz.toml`.
This is the main option you will want to set:

- `ssh_key`: Path to the SSH private key file to use when connecting to instances.

You can also configure Chazz for your AWS setup (the defaults are for the Capra AWS account):

- `key_name`: The name of the key pair in AWS. Chazz will attach this to any new instances it creates. It should be the key pair corresponding to the `ssh_key` file above.
- `security_group`: The AWS security group to associate with new instances. You'll want to (manually) create a security group that allows SSH connections.
- `default_ami`: The name (i.e., version) of the AMI to connect to and to use for new instances. This is like the `-i` command-line flag (below).

There are also some other options you probably don't need to change.
See [the default configuration][default] for an exhaustive list and an example of what a config file looks like.

[toml]: https://github.com/toml-lang/toml
[default]: https://github.com/cucapra/chazz/blob/master/chazz/config_default.toml

### Options

There are a few global command-line flags you can use:

* `--ami`: Pick a specific AMI ID to connect to or launch.
* `-i`: A shorthand to pick an AMI from our built-in list. Use the version name string. For example, `-i v0.4.2` will start and connect to instances using that version of the image.

[rsync]: https://www.samba.org/rsync/
[watchexec]: https://github.com/watchexec/watchexec
