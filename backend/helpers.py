from boto3 import Session as BotoSession
from botocore.exceptions import ClientError
import json
import os


def get_secret_dict_from_id(secret_id, client):
    try:
        secret_string = json.loads(client.get_secret_value(SecretId=secret_id)).get(
            "SecretString"
        )
    except ClientError as e:
        raise e
    return json.loads(secret_string)


def load_aws_secrets():
    secret_ids = ("quaigle", "sentry")
    region_name = "eu-central-1"

    # Create a Secrets Manager client
    session = BotoSession()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    # load all secrets into the environment
    for secret_id in secret_ids:
        secret_dict = get_secret_dict_from_id(secret_id, client)
        for secret_key, secret_value in secret_dict.items():
            os.environ[secret_key] = secret_value
