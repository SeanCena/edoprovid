# EDOProVid [<img src="https://img.shields.io/badge/invite%20to-discord-brightgreen?style=for-the-badge" alt="Invite to Discord" align="right" />](https://discord.com/api/oauth2/authorize?client_id=1145976977321377842&permissions=277025426432&scope=bot)

<img src="docs/img/logo.png" style="align: center;" height=200px/>

EDOProVid is a Discord bot that converts replay files for the Yu-Gi-Oh simulator EDOPro into videos. The mechanism behind EDOProVid is super straightforward: run EDOPro on an Autoscaling EC2 instance and use ffmpeg to record the output. Everything is written in Python using the Discord.py library and runs on Ubuntu 22.04.

_Please note that CI/CD pipelines are not in place yet, so until I set those up, I will manually update the EC2 instances when changes are committed to the repo. Archaic, I know._

## Discord Permissions

The EDOProVid bot requires the following permissions:

- Read messages/view channels
- Send messages
- Send messages in threads
- Attach files
- Read message history
- Use slash commands

## Don't try this at home (self-hosting)

It's not a safety thing, it's just super tedious to set up. Preparing all the resources in AWS is a hassle and I don't want you to suffer through that. Just wait until CloudFormation support is added.

## To do

- CI/CD using CodeDeploy
- Use IaC system, probably CloudFormation
- Integrate slash commands
- Move the AWS keys off the EC2 instances
- Have the recorder machine reboot after timing out
