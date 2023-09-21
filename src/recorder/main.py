import boto3
from botocore.config import Config
from datetime import datetime
from dotenv import load_dotenv
import json
import os
from PIL import Image
import pyautogui
import subprocess
import time

load_dotenv()

prefix = '!'  # Can change this later
edopro_path = os.path.expanduser('~/ProjectIgnis')
winw, winh = 1000, 600  # screen dimensions

edoprovid_config = Config(region_name='us-west-1',
                          signature_version='v4',
                          retries={
                              'max_attempts': 10,
                              'mode': 'standard'
                          })
s3 = boto3.client('s3', config=edoprovid_config)
sqs = boto3.client('sqs', config=edoprovid_config)
autoscaling = boto3.client('autoscaling', config=edoprovid_config)

BUCKET_NAME = os.environ['BUCKET_NAME']
IN_QUEUE_URL = os.environ['IN_QUEUE_URL']
OUT_QUEUE_URL = os.environ['OUT_QUEUE_URL']
EC2_INSTANCE_ID = os.environ['EC2_INSTANCE_ID']


def main():
    """Polls inbound queue, records replay file, uploads mp4, updates outbound queue"""
    loop_count = 0
    while loop_count < 2:  # Quits main loop after 2 * 20 seconds of idling (TODO: change back to 2)
        try:
            # Poll queue
            response = sqs.receive_message(QueueUrl=IN_QUEUE_URL,
                                           AttributeNames=['All'],
                                           WaitTimeSeconds=20,
                                           MaxNumberOfMessages=1)
            if response is not None and response.get('Messages') is not None:
                message = response['Messages'][0]
                receipt_handle = message['ReceiptHandle']
                sqs.delete_message(QueueUrl=IN_QUEUE_URL,
                                   ReceiptHandle=receipt_handle)
                response_json = json.loads(message['Body'])
                file_id, file_name, owner, channel_id = response_json[
                    'file_id'], response_json['file_name'], response_json[
                        'owner'], response_json['channel']

                # Clear replays, then download replay file from S3 to ~/edoprovid/ProjectIgnis/replay/
                os.system('rm ' + os.path.join(edopro_path, 'replay/*'))
                s3.download_file(
                    BUCKET_NAME, f'{file_id}.yrpX',
                    os.path.join(edopro_path, f'replay/{file_id}.yrpX'))

                # Convert file
                convert(file_id)

                # Upload mp4
                s3.upload_file(f'/tmp/{file_id}.mp4', BUCKET_NAME,
                               f'{file_id}.mp4')

                # Update outbound queue
                sqs.send_message(QueueUrl=OUT_QUEUE_URL,
                                 MessageBody=json.dumps({
                                     'file_id': file_id,
                                     'file_name': file_name,
                                     'owner': owner,
                                     'channel': channel_id
                                 }),
                                 MessageDeduplicationId=file_id,
                                 MessageGroupId='outbound')
                loop_count = 0
            else:
                loop_count += 1

        except Exception as e:
            print(f'{datetime.now()} - {str(e)}')


def convert(file_id):
    """Converts the replay file to mp4"""

    # SIGCONT EDOPro
    os.system('pkill -18 EDOPro')

    # Maximize EDOPro window and enter replay
    os.system("wmctrl -r 'Project Ignis: EDOPro' -b add,fullscreen")
    os.system("wmctrl -a 'Project Ignis: EDOPro'")
    time.sleep(0.5)
    pyautogui.click(500, 346)  # Click replays button
    time.sleep(0.5)
    pyautogui.click(266, 137)  # Select first replay
    time.sleep(0.5)
    pyautogui.click(742, 468)  # Enter replay
    pyautogui.moveTo(10, 10)  # Move mouse away from screen

    # Start subprocess for ffmpeg screen recording
    x, y, w, h = 322, 4, 676, 594
    rec = subprocess.Popen(
        f'ffmpeg -y -video_size {w}x{h} -framerate 24 -f x11grab -i :0.0+{x},{y} -pix_fmt yuv420p -c:v libx264 -crf 35 -preset ultrafast -an /tmp/{file_id}.mp4',
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=True)

    # Detect when replay is finished (the "replay ended" box appears)
    x, y, w, h = 581, 225, 256, 77
    total, div = 1, 2  # (total) seconds of solid white, checking every (total/div) seconds
    white = Image.new('RGB', (w, h), (255, 255, 255))
    count = 0
    while count < div:
        time.sleep(total / div)
        section = pyautogui.screenshot(region=(x, y, w, h))
        count = (count + 1) * (
            section == white
        )  # chat, is this marginally faster than an if-statement?

    # End ffmpeg screen recording
    rec.communicate(b'q\n')

    # Back to EDOPro main menu
    pyautogui.click(667, 317)  # Exit replay
    time.sleep(0.5)
    pyautogui.click(738, 498)  # Exit replay menu
    time.sleep(0.5)

    # SIGSTOP EDOPro
    os.system('pkill -19 EDOPro')


if __name__ == "__main__":
    main()
    # Terminate instance in autoscaling
    try:
        response = autoscaling.terminate_instance_in_auto_scaling_group(
            InstanceId=EC2_INSTANCE_ID, ShouldDecrementDesiredCapacity=True)
    except Exception as e:
        print(f'{datetime.now()} - {str(e)}')