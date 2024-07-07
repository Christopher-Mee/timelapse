# timelapse

* Step 1) Obtain your timelapse photos  
  * Install your raspberry pi camera. (I will not include a guide.)  
  * Install camera.sh script to your raspberry pi.  
    * Transfer or download the script to your pi.
    * Create a new dir /home/pi/timelapse/ and store the script inside.  
    * Open Terminal:  
      Ctrl + Alt + T  
    * Run:  
      sudo crontab -e  
    * Add:  
      \* \* \* \* \* sh /home/pi/timelapse/camera.sh 2>&1  
    * Exit:  
      Ctrl + x , then Y
  * Tips:  
    * To disable your timelapse, delete the line from crontab or add a # before the line.
    * If you need to flip the camera, modify the camera.sh script.
      * ex. raspistill -hf -vf -o /home/pi/timelapse/$DATE.jpg
      * -hf horizontal flip
      * -vf vertical flip
    * The timelapse will take one photo per minute.
    * The output will be stored in the new dir you created to store the scirpt.
