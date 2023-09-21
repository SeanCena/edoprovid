#!/bin/bash

export EC2_INSTANCE_ID="`wget -q -O - http://169.254.169.254/latest/meta-data/instance-id`"
Xvfb :0 -screen 0 1000x600x24 &
/home/ubuntu/ProjectIgnis/EDOPro &
sleep 6           # wait for all the alert boxes to finish
pkill -19 EDOPro  # pause EDOPro so it doesn't consume resources
python3 /home/ubuntu/edoprovid-bot/src/main.py > ./edoprovid.log