import boto3
from botocore.config import Config
from datetime import datetime
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import json
import math
import os
import time
import traceback
import uuid

load_dotenv()

edoprovid_config = Config(
    region_name = 'us-west-1',
    signature_version = 'v4',
    retries = {
        'max_attempts': 10,
        'mode': 'standard'
    }
)
s3 = boto3.client('s3', config=edoprovid_config)
sqs = boto3.client('sqs', config=edoprovid_config)
cloudwatch = boto3.client('cloudwatch', config=edoprovid_config)
autoscaling = boto3.client('autoscaling', config=edoprovid_config)

BUCKET_NAME = os.environ['BUCKET_NAME']
IN_QUEUE_URL = os.environ['IN_QUEUE_URL']
OUT_QUEUE_URL = os.environ['OUT_QUEUE_URL']
CW_NAMESPACE = os.environ['CW_NAMESPACE']
AUTOSCALING_GROUP = os.environ['AUTOSCALING_GROUP']

prefix = '!'       # Find out how to change prefixes
cmd_1 = 'record'   # Dunno if this is the best
waiting_count = 0  # Number of items in queue and currently being processed

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=prefix, intents=intents)


@bot.event
async def on_ready():
    send_outbound_videos.start()
    update_cloudwatch_metrics.start()
    print(f'{datetime.now()} - Bot is logged in as {bot.user}')


@bot.command(name=cmd_1)
async def convert(ctx, *args):
    message = ctx.message
    if len(message.attachments) == 0:
        await ctx.channel.send(f'No attachment found. Type `{prefix}{cmd_1}` in the message box and attach a replay file.')
    elif len(message.attachments) > 1:
        await ctx.channel.send(f'More than one attachment found. `{prefix}{cmd_1}` accepts only one replay file at a time.')
    else:
        try:
            # Verify that the file header is correct
            file_id = uuid.uuid4().hex
            file_path = f'/tmp/{file_id}.yrpX'
            file_name = message.attachments[0].filename
            await message.attachments[0].save(file_path)
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header != b'yrpX':
                    await ctx.channel.send(f'Invalid or corrupted file. `{prefix}{cmd_1}` accepts .yrpX files only.')
                    return False
            await ctx.channel.send('Adding file to queue...')

            # Upload replay to S3
            response = s3.upload_file(file_path, BUCKET_NAME, f'{file_id}.yrpX')

            # Put file id on SQS
            response = sqs.send_message(
                QueueUrl=IN_QUEUE_URL,
                MessageBody=json.dumps({
                    'file_id': file_id,
                    'file_name': file_name,
                    'owner': message.author.mention,
                    'channel': ctx.channel.id
                }),
                MessageDeduplicationId=file_id,
                MessageGroupId='inbound'
            )
            global waiting_count
            waiting_count += 1
            await ctx.channel.send(f'File `{file_name}` added to queue in position {waiting_count}.')

            # If necessary, increase autoscaling desired capacity to math.ceil(waiting_count/2)
            response = autoscaling.describe_auto_scaling_groups(
                AutoScalingGroupNames=[AUTOSCALING_GROUP],
                MaxRecords=1
            )
            if response is not None and response.get('AutoScalingGroups') is not None:
                current_cap = response['AutoScalingGroups'][0]['DesiredCapacity']
                max_cap = response['AutoScalingGroups'][0]['MaxSize']
                optimal_cap = math.ceil(waiting_count/2)
                if current_cap < optimal_cap and optimal_cap <= max_cap:
                    autoscaling.set_desired_capacity(
                        AutoScalingGroupName=AUTOSCALING_GROUP,
                        DesiredCapacity=optimal_cap
                    )
                if current_cap == 0:
                    await ctx.channel.send(':alarm_clock: *Currently waking the servers from their nap. This request might take longer than usual to complete.*')

        except Exception as e:
            await ctx.channel.send(f'`An error occurred!\n{traceback.format_exc()}`')
            print(f'{datetime.now()} - {traceback.format_exc()}')


@tasks.loop(seconds=2.5, count=None)
async def send_outbound_videos():
    """Continuously check the outbound SQS queue and send any recently finished videos"""
    start_time = time.time()
    while time.time() - start_time < 1.0:
        try:
            response = sqs.receive_message(
                QueueUrl=OUT_QUEUE_URL,
                AttributeNames=['All'],
                WaitTimeSeconds=1,
                MaxNumberOfMessages=5
            )
            if response is not None and response.get('Messages') is not None:
                for message in response['Messages']:
                    receipt_handle = message['ReceiptHandle']
                    sqs.delete_message(
                        QueueUrl=OUT_QUEUE_URL,
                        ReceiptHandle=receipt_handle
                    )
                    global waiting_count
                    waiting_count -= 1
                    response_json = json.loads(message['Body'])
                    file_id, file_name, owner, channel_id = response_json['file_id'], response_json['file_name'], response_json['owner'], response_json['channel']
                    s3.download_file(BUCKET_NAME, f'{file_id}.mp4', f'/tmp/{file_id}.mp4')
                    await bot.wait_until_ready()
                    channel = bot.get_channel(channel_id)
                    await channel.send(f'{owner}, your recording of `{file_name}` is ready.', file=discord.File(f'/tmp/{file_id}.mp4'))
        except Exception as e:
            print(f'{datetime.now()} - {traceback.format_exc()}')


@tasks.loop(seconds=30, count=None)
async def update_cloudwatch_metrics():
    """Update Cloudwatch metrics"""
    try:
        response = cloudwatch.put_metric_data(
            Namespace=CW_NAMESPACE,
            MetricData=[
                {
                    'MetricName': 'waiting_count',
                    'StatisticValues': {  # do not ask me how long i spent trying to spell statistic
                        'SampleCount': 1.0,
                        'Sum': waiting_count * 1.0,
                        'Minimum': waiting_count * 1.0,
                        'Maximum': waiting_count * 1.0
                    },
                    'Unit': 'Count',
                    'StorageResolution': 60
                }
            ]
        )
    except Exception as e:
        print(f'{datetime.now()} - {traceback.format_exc()}')



if __name__ == "__main__":
    bot.run(os.environ['TOKEN'])