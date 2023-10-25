"""A code as infrastructure pulumi program to set-up an ec2 instance"""

import pulumi
from pulumi_aws import ec2, iam

# import pulumi_command as command
import json

# import base64
import os

stack_name = pulumi.get_stack()

config = pulumi.Config()
key_name = config.get("keyName")


# def decode_key(key):
#     # taken from
#     # https://github.com/pulumi/examples/blob/master/aws-py-ec2-provisioners/__main__.py
#     try:
#         key = base64.b64decode(key.encode("ascii")).decode("ascii")
#     except:
#         pass
#     if key.startswith("-----BEGIN RSA PRIVATE KEY-----"):
#         return key
#     return key.encode("ascii")


# private_key = config.require_secret("privateKey").apply(decode_key)

# storage_size = 50

# Create a security group for the instances
security_group_http = ec2.SecurityGroup(
    "web-secgrp",
    description="Enable HTTP and SSH access",
    ingress=[
        {
            "protocol": "tcp",
            "from_port": 8000,
            "to_port": 8000,
            "cidr_blocks": ["0.0.0.0/0"],
        },
        {
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "cidr_blocks": ["0.0.0.0/0"],
        },
    ],
    # egress=[
    #     {
    #         'protocol': 'tcp',
    #         'from_port': 443,  # https
    #         'to_port': 443,
    #         'cidr_blocks': ['0.0.0.0/0'],
    #     },
    # ]
)


# ami_id = pulumi.Output.from_input(instance_ami)

# Get the AMI
# ami = ec2.get_ami(
#     owners=['amazon'],
#     most_recent=True,
#     filters=[ec2.GetAmiFilterArgs(
#         name='name',
#         values=['amzn2-ami-hvm-*-x86_64-gp2'],
#     )],
# )

# https://www.pulumi.com/registry/packages/aws/api-docs/ec2/getamiids/
ubuntu = ec2.get_ami_ids(
    filters=[
        ec2.GetAmiIdsFilterArgs(
            name="name",
            values=["ubuntu/images/ubuntu-*-*-amd64-server-*"],
        )
    ],
    owners=["099720109477"],
)


# To view logs run `journalctl -u prefect-agent.service` in a terminal on the EC2


# Specify root block device and add some extra storage
# root_block_device = ec2.InstanceRootBlockDeviceArgs(
#     volume_size=storage_size,
#     volume_type='gp2',
#     delete_on_termination=True,
# )


# Create an IAM role for the EC2 instance
ec2_role = iam.Role(
    "ec2Role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                }
            ],
        }
    ),
)

# Create a policy for CloudWatch Logs access
ec2_logs_policy = iam.Policy(
    "ec2LogsPolicy",
    description="A policy to allow EC2 instances to send logs to CloudWatch",
    policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams",
                    ],
                    "Effect": "Allow",
                    "Resource": "arn:aws:logs:*:*:*",
                }
            ],
        }
    ),
)

# Attach the policy to the EC2 role
ec2_logs_policy_attachment = iam.RolePolicyAttachment(
    "ec2LogsPolicyAttachment",
    policy_arn=ec2_logs_policy.arn,
    role=ec2_role.name,
)

# Create an instance profile and associate the role with it
ec2_instance_profile = iam.InstanceProfile("ec2InstanceProfile", role=ec2_role.name)

docker_url = "https://download.docker.com/linux/ubuntu"
install_docker = f"""sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL {docker_url}/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources:
echo \
  "deb [arch="$(dpkg --print-architecture)" \
  signed-by=/etc/apt/keyrings/docker.gpg] {docker_url} \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
"""

run_docker_image = f"""
    export GIT_TOKEN={os.getenv("GIT_TOKEN")}
    docker login --username name --password GIT_TOKEN ghcr.io
    docker run ghcr.io/{os.getenv("GIT_NAME")}/{os.getenv("APP_NAME")}:latest
    """
user_data = install_docker + run_docker_image


# Create an EC2 instance
ec2_instance = ec2.Instance(
    f"{stack_name}-instance",
    instance_type="t2.micro",
    ami=ubuntu,
    # vpc_security_group_ids=[security_group_http.id],
    user_data=user_data,
    key_name="fastapiapp",
    # root_block_device=root_block_device,
    tags={f"{stack_name}-instance"},
    iam_instance_profile=ec2_instance_profile.name,
)

# Create a connection to the EC2 instance
# https://github.com/pulumi/examples/blob/master/aws-py-ec2-provisioners/__main__.py
# private key needs to be the string from the aws *.pem key file sored in pulumi secrets
#
# connection = command.remote.ConnectionArgs(
#     host=ec2_instance.public_ip,
#     # user='ec2-user',
#     user="ubuntu",
# pem file string which needs to be read from the pulumi secrets
#     private_key=private_key,
# )

# # Copy a config file to our server.
# cp_config = command.remote.CopyFile(
#     "config",
#     connection=connection,
#     local_path="myapp.conf",
#     remote_path="myapp.conf",
#     opts=pulumi.ResourceOptions(depends_on=[ec2_instance]),
# )

# # Execute a basic command on our server.
# cat_config = command.remote.Command(
#     "cat-config",
#     connection=connection,
#     create="cat myapp.conf",
#     opts=pulumi.ResourceOptions(depends_on=[cp_config]),
# )


pulumi.export("ec2_instance_id", ec2_instance.id)
pulumi.export("instance_public_ip", ec2_instance.public_ip)
pulumi.export("instance_public_dns", ec2_instance.public_dns)


# https://www.learnaws.org/2021/06/19/pulumi-python-ec2/
# https://github.com/pulumi/examples/blob/master/aws-py-ec2-provisioners/__main__.py
# https://github.com/jonashackt/pulumi-python-aws-ansible/blob/master/README.md#ssh-connection-to-the-pulumi-created-ec2-instance
