Chazz: A Tool for Running HammerBlade in F1
===========================================

This is a little utility for interacting with HammerBlade machines running in [F1][].
It's another [*Blades of Glory*][bog] reference.

[f1]: https://aws.amazon.com/ec2/instance-types/f1/
[bog]: https://www.imdb.com/title/tt0445934/


Set Up
------

First, set up your [AWS configuration][config].
You can type `aws configure` (if you have the AWS CLI) or manually create the files.
On a shared account, you may need to create yourself an [IAM user][iam] with "programmatic access" to get an access key.
Use the `us-west-2` (Oregon) region.

Next, obtain the private key and put it here.
The filename is currently hard-coded as `ironcheese.pem`.
Make sure the permissions are right:

    $ chmod 0600 ironcheese.pem

Finally, install the dependencies for this tool:

    $ pip install --user -r requirements.txt

[config]: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#configuration
[iam]: https://console.aws.amazon.com/iam/home?#/users


Use
---

Type `python3 chazz.py` to see a list of available commands.
