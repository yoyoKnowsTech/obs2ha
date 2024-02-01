# obs2ha
Control OBS from Home Assistant

This script allows you to control OBS from Home Assistant using MQTT - It will allow you to....

1. Control Audio levels, and mute
2. Control Scenes
3. Start / Stop Virtual Camera, Recording and Streaming from HA

This script was cobbled together from a number of sources - I have left links to originals, but to be honest don't remember where everything came from!

I am running this on my Mac Studio to act as a bridge between OBS and Home Assistant - It should be able to be run anywhere and it will communicate over the network.

USE and Setup

First time you run it you will need to install the Mac developer tools - it should prompt you to install.

You will need to add these two dependancies

pip3 install paho.mqtt  
pip3 install obs-websocket-py

In OBS, enable websocket --> copy username, password ip and socket to the script
In Home Assistant install MQTT Broker, create a HA user and copy username, password, port and IP to the script

Run the script - If you close or restart OBS or Home Assistant it should try to reconnect every 30 seconds.

This script needs to continue running in order to control OBS