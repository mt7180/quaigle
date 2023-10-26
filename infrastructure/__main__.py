"""A code as infrastructure pulumi program to set-up an ec2 instance"""

import pulumi
from pulumi_aws import ec2, iam

import json

# get secret openai api key
# config = pulumi.Config()
# openai_key = ssm.Parameter(
#     "openai_key", type="SecureString", value=config.require_secret("openai_key")
# )

# EC2 Instance Configuration
ec2_instance_name = f"{pulumi.get_project()}_{pulumi.get_stack()}"
ec2_image_id = "ami-06dd92ecc74fdfb36"
ec2_instance_type = "t2.micro"
# ec2_storage_size = 50


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
    # neccessary for docker installation:
    egress=[
        {
            "protocol": "tcp",
            "from_port": 443,  # https
            "to_port": 443,
            "cidr_blocks": ["0.0.0.0/0"],
        },
        {
            "protocol": "tcp",
            "from_port": 80,
            "to_port": 80,
            "cidr_blocks": ["0.0.0.0/0"],
        },
    ],
)

ubuntu_ami = pulumi.Output.from_input(ec2_image_id)

# Specify root block device and add some extra storage
# root_block_device = ec2.InstanceRootBlockDeviceArgs(
#     volume_size=ec2_storage_size,
#     volume_type='gp2',
#     delete_on_termination=True,
# )


# Create IAM role for the EC2 instance (standard - yes, 2017!)
ec2_iam_role = iam.Role(
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
# ec2_logs_policy = iam.Policy(
#     "ec2LogsPolicy",
#     description="A policy to allow EC2 instances to send logs to CloudWatch",
#     policy=json.dumps(
#         {
#             "Version": "2012-10-17",
#             "Statement": [
#                 {
#                     "Action": [
#                         "logs:CreateLogGroup",
#                         "logs:CreateLogStream",
#                         "logs:PutLogEvents",
#                         "logs:DescribeLogStreams",
#                     ],
#                     "Effect": "Allow",
#                     "Resource": "arn:aws:logs:*:*:*",
#                 }
#             ],
#         }
#     ),
# )

# Create a policy for CloudWatch Logs access
# https://docs.aws.amazon.com/mediaconnect/latest/ug/iam-policy-examples-asm-secrets.html
ec2_sec_man_policy = iam.Policy(
    "ec2SecManPolicy",
    description="A policy to allow EC2 instances read access to specific resources \
     (secrets) that you create in AWS Secrets Manager.",
    policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetResourcePolicy",
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret",
                        "secretsmanager:ListSecretVersionIds",
                    ],
                    "Resource": [
                        "arn:aws:secretsmanager:eu-central-1:039166537875:secret:quaigle-jW3M0i",
                        "arn:aws:secretsmanager:eu-central-1:039166537875:secret:sentry-9Q4Cqm",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": "secretsmanager:ListSecrets",
                    "Resource": "*",
                },
            ],
        }
    ),
)

# Attach the logs policy to the EC2 role
# ec2_logs_policy_attachment = iam.RolePolicyAttachment(
#     "ec2LogsPolicyAttachment",
#     policy_arn=ec2_logs_policy.arn,
#     role=ec2_role.name,
# )

# Attach the sec manager policy to the EC2 role
ec2_sec_man_policy_attachment = iam.RolePolicyAttachment(
    "ec2SecManPolicyAttachment",
    policy_arn=ec2_sec_man_policy.arn,
    role=ec2_iam_role.name,
)

# Create an instance profile and associate the role with it
ec2_iam_instance_profile = iam.InstanceProfile(
    "ec2InstanceProfile", role=ec2_iam_role.name
)

# Create user_data string
docker_url = "https://download.docker.com/linux/ubuntu"

install_docker = f"""sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL {docker_url}/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" \
  signed-by=/etc/apt/keyrings/docker.gpg] {docker_url} \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
"""

user_data = install_docker

# Create an EC2 instance
ec2_instance = ec2.Instance(
    "quaigle_aws_ec2_ubuntu",
    instance_type=ec2_instance_type,
    ami=ubuntu_ami,
    vpc_security_group_ids=[security_group_http.id],
    # user_data=user_data,
    key_name="key_eu_central_1",
    # root_block_device=root_block_device,
    metadata_options=ec2.InstanceMetadataOptionsArgs(
        http_put_response_hop_limit=3,
    ),
    tags={
        "Name": ec2_instance_name,
    },
    iam_instance_profile=ec2_iam_instance_profile.name,
)

pulumi.export("ec2_instance_id", ec2_instance.id)
pulumi.export("instance_public_ip", ec2_instance.public_ip)
pulumi.export("instance_public_dns", ec2_instance.public_dns)


# https://www.learnaws.org/2021/06/19/pulumi-python-ec2/
# https://github.com/pulumi/examples/blob/master/aws-py-ec2-provisioners/__main__.py
# https://github.com/jonashackt/pulumi-python-aws-ansible/blob/master/README.md#ssh-connection-to-the-pulumi-created-ec2-instance
