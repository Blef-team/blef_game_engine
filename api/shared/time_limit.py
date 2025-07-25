import os
import boto3
import json
from botocore.exceptions import ClientError
from .response import DecimalEncoder

sqs_client = boto3.client("sqs")
TIME_LIMIT_QUEUE_NAME = os.environ.get("time_limit_queue_name")

def get_time_limit_queue_url():
    """
    Returns the URL of the time limit SQS queue.
    """
    try:
        return sqs_client.get_queue_url(QueueName=TIME_LIMIT_QUEUE_NAME)['QueueUrl']
    except ClientError:
        return None

def send_time_limit_message(game_uuid, player_uuid, round_number, time_limit, history_len):
    """
    Sends a delayed message to the SQS queue to trigger a timeout check.
    """
    queue_url = get_time_limit_queue_url()
    if not queue_url:
        print("Warning: Time limit queue URL not found.")
        return

    try:
        payload = {
            "game_uuid": game_uuid,
            "player_uuid": player_uuid,
            "round_number": round_number,
            "history_len": history_len
        }
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload, cls=DecimalEncoder),
            DelaySeconds=time_limit
        )
    except ClientError as e:
        print(f"Error sending SQS message: {e}")
        pass
