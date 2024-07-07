#!/bin/bash
DATE=$(date +"%Y-%m-%d_%H%M")
raspistill -hf -vf -o /home/pi/timelapse/$DATE.jpg
#raspistill -o /home/pi/timelapse/$DATE.jpg
