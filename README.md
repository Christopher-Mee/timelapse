# timelapse

Generate a video to view your raspberry pi timelapse.

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
* Step 2) Transfer your timelapse photos to your windows pc.
  * USe a flash drive, use SFTP, or upload to the cloud.
 * Step 3) Install FFmpeg  
   * [Download the latest build](https://www.gyan.dev/ffmpeg/builds/)
   * Move to a location of your choosing.
     * ex: C:\bin
   * Add to PATH
     * Press windows key, then search (start typing) 'path'.
     * Select the first result.
     * Select Environment Variables (located at the bottom of the new window).
     * under User variables double click path.
     * Select browse, go to your choosen location, then select the bin folder inside.
     * select ok on each window until all are closed.
     * Open cmd and type FFmpeg to test.
