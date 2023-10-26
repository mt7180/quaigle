from boto3 import Session as BotoSession
from botocore.exceptions import ClientError
import os


def get_secret_value_from_client(secret, client):
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret)
    except ClientError as e:
        raise e
    # Decrypt secrets using the associated KMS key.
    print(f"test: {get_secret_value_response['SecretString']}")
    return get_secret_value_response["SecretString"]


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
