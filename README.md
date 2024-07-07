# timelapse

Generate a video to view your raspberry pi timelapse.

The following is a hyper detailed installation guide. Do not be intimidated.  
* ‎**1) Obtain your timelapse photos**
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
        
* **‎2) Transfer your timelapse photos to your windows pc.**
  * Your timelpase output is stored in the scirpt dir, created in step 1.
  * Use a flash drive, SFTP, or upload to the cloud.
      
* ‎**3) Install FFmpeg on your pc**  
   * [Download the latest release](https://www.gyan.dev/ffmpeg/builds/)
     * Located under 'release builds'
   * Move to a location of your choosing.
     * ex: C:\bin
   * Add to PATH
     * Press windows key, then search (start typing) 'path'.
     * Select the first result.
     * Select Environment Variables (located at the bottom of the new window).
     * Under 'User Variables', double click path.
     * Select browse, go to your choosen location, then select the ffmpeg folder, then the bin folder.
     * Select ok on each window until all are closed.
     * Open cmd and type 'FFmpeg' to test.
      
* ‎**4) Install python script on your pc**  
  * install [python](https://www.python.org/downloads/) version 3.10+
  * select an install location
  * Open install location, hold shift and left click, select open cmd/powershell
  * clone repo  
  * python -m venv venv  
  * python -m pip install --upgrade pip  
  * pip install -r requirements.txt --use-pep517
