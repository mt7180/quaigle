from boto3 import Session as BotoSession
from botocore.exceptions import ClientError
import os


def get_secret_value_from_client(secret, client):
    try:
        secret_string = client.get_secret_value(SecretId=secret).get("SecretString")
    except ClientError as e:
        raise e

    return secret_string.split("\\")[-2][1:]


def load_aws_secrets():
    secrets = ("quaigle", "sentry")
    region_name = "eu-central-1"

    # Create a Secrets Manager client
    session = BotoSession()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    # tuple unpacking into env vars
    os.environ["OPENAI_API_KEY"], os.environ["SENTRY_SDK"] = tuple(
        [get_secret_value_from_client(secret, client) for secret in secrets]
    )
