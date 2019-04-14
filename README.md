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
Use the `us-west-2` (Oregon) region.

Next, obtain the private key and put it here.
Make sure the permissions are right:

    $ chmod 0600 ironcheese.pem

You can either use that name or set the `CHAZZ_KEY` environment variable to point to the key file:

    $ export CHAZ_KEY=`pwd`/ironcheese.pem

[config]: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#configuration
[iam]: https://console.aws.amazon.com/iam/home?#/users


Use
---

Type `chazz` to see a list of available commands.

To boot up an instance and SSH into it, type `chazz ssh`.
Before giving you a prompt, the tool runs a command to load the FPGA configuration.
Use the instance like normal, then disconnect.
Type `chazz stop` to stop the instance (and stop paying for it).

You can see a list of available HammerBlade instances with `chazz list`.
