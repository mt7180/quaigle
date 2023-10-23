# How-To get started with pulumi & AWS
---
link to the docs: https://www.pulumi.com/docs/

### pre-requisites
- create a pulumi account on website
- install pulumi cli (on macOS: brew install pulumi/tap/pulumi)
- create an account for aws
- create an ami user with permission for e.g. AmazonFullAcessEC2 or S3 in the aws management console in access management / Users => aws_access_key_id
- after creating the ami user, clic on the user name and open the tab security credentials, create an access key for programmatical access (aws_secret_access_key)
- install aws cli (on mac: brew install awscli)
- run command "aws configure", you will be prompted for AWS Access Key ID and AWS Secret Access Key => a credentials file is created in user dir: ~/.aws/credentials
   
### setting up the pulumi project

- create a sub-folder in your project folder (e.g. "infrastructure") which is empty.
- execute command: "pulumi new aws-python" and enter project name, project description, the deired stack name (dev) and the AWS regiion (eu-central-1) -> a python venv is created within this folder and the necessary libraries are installed (pulumi & pulumi-aws ...)
- run pulumi up => pulumi plans the steps defined in __main__.py (an initial s3 bucket template is added per default")
- if you confirm by selecting "yes", the steps are executed and if you didn't change the template, a s3 bucket is created. You can check with "aws s3 ls" command
- now you can edit and configure the __main__.py file according to your needs

