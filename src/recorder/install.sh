#!/bin/bash

# install packages
sudo apt install python3-pip
sudo apt install xvfb
sudo apt install ffmpeg
sudo apt install scrot

# install and extract edopro
wget https://github.com/ProjectIgnis/edopro-assets/releases/download/40.1.4/ProjectIgnis-EDOPro-40.1.4-linux.tar.gz
tar -xzvf ProjectIgnis-EDOPro-40.1.4-linux.tar.gz
mv ./ProjectIgnis/ ~/

# change edopro settings
cat system.conf > ~/ProjectIgnis/config/system.conf

# install pip packages
pip3 install -r requirements.txt