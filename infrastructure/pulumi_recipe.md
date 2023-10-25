# How-To get started with pulumi & AWS & python
---
link to the docs: https://www.pulumi.com/docs/

### pre-requisites
- create a pulumi account on website
- install pulumi cli (on macOS: brew install pulumi/tap/pulumi)
- create an account for aws
- create an iam user with permission for e.g. AmazonFullAcessEC2 or S3 in the aws management console in access management / Users => aws_access_key_id
- after creating the iam user, clic on the user name and open the tab security credentials, create an access key for programmatical access (aws_secret_access_key)
- install aws cli (on mac: brew install awscli)
- run command "aws configure", you will be prompted for AWS Access Key ID and AWS Secret Access Key => a credentials file is created in user dir: ~/.aws/credentials
   
### setting up the pulumi project

- create a sub-folder in your project folder (e.g. "infrastructure") which is empty.
- execute command: "pulumi new aws-python". First you have to login by Personal access token, follow the given link and create one and paste it- Then enter project name, project description, the desired stack name (dev) and the AWS regiion (eu-central-1) -> a python venv is created within this folder and the necessary libraries are installed (pulumi & pulumi-aws ...)
- run pulumi up => pulumi plans the steps defined in __main__.py (an initial s3 bucket template is added per default")
- if you confirm by selecting "yes", the steps are executed and if you didn't change the template, a s3 bucket is created. You can check with "aws s3 ls" command
- now you can edit and configure the __main__.py file according to your needs

### Pulumi AI answer regarding AWS key pair:
The key.pem file, which represents the SSH key pair, typically needs to be located on the machine where you are going to run your Pulumi program.

However, the path of the key.pem file is not set inside the Pulumi program itself. Rather, it's a detail that would be of interest to the SSH client which will connect to the corresponding EC2 instance.

In your Pulumi program, you mention the key_name which refers to the name of the key pair on AWS services, not the key.pem file on your local machine.

Remember that the key.pem file should be securely stored as it provides access to your EC2 instances. It must not be embedded or referenced directly in your Pulumi program for security reasons.

One way to manage key pairs with Pulumi in a secure way is to create them dynamically within your Pulumi program and save the private key securely. Then, set the key_name of the aws.ec2.Instance to the dynamically generated key pair. Note that this would be a change to your current deployment setup. Let me know if you'd like to proceed in this direction!
