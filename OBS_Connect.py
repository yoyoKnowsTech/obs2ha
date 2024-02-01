#!/usr/bin/env python3

# https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md#setinputmute
# https://wiki.streamer.bot/en/Broadcasters/OBS/Events
# https://obsproject.com/kb/macos-desktop-audio-capture-guide


import sys
#import time
import json

import socket # Just so we can properly handle hostname exceptions
import paho.mqtt.client as mqtt
#import ssl
import pathlib
#import time
import enum
import uuid
from random import randrange, uniform

import logging
'''logging.basicConfig(level=logging.DEBUG)'''

sys.path.append('../')
from obswebsocket import obsws, events, requests  # noqa: E402

host = "10.0.2.134"
port = 4455
password = "yourOBSPassword"
authreconnect = 30

INTERVAL = 5 # Update interval (in seconds)
MQTT_HOST = "10.0.1.160" # Hostname of your MQTT server
MQTT_USER = "obs"
MQTT_PW = "yourHomeAssistantMQTTUserPassword"
MQTT_PORT = 1883 # Default MQTT port is 1883
MQTT_BASE_CHANNEL = "homeassistant"
MQTT_SENSOR_NAME = "OBS2HA"
PROFILES = []
STREAM_SWITCH = None
RECORD_SWITCH = None
VIRTUALCAM_SWITCH = None
SENSOR = None
CONTROL = True
DEBUG = False
LOCK = False
MAC = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
		 for ele in range(0,8*6,8)][::-1])
SCENES = []
MUTE_SWITCHES = []
VOLUME_SWITCHES = []


# Meta
__version__ = '1.1'
__version_info__ = (1, 0, 1)
__license__ = "AGPLv3"
__license_info__ = {
    "AGPLv3": {
        "product": "update_mqtt_status_homeassistant",
        "users": 0, # 0 being unlimited
        "customer": "Unsupported",
        "version": __version__,
        "license_format": "1.0",
    }
}
__author__ = 'yoyoKnows_tech'

__doc__ = """\
Publishes real-time OBS status info to the given MQTT server/port/channel \
at the configured interval. Also opens up controllable aspects of OBS to \
be controlled through MQTT.
"""

def on_event(message):
    print("Got a message from OBS: {}".format(message))

     # Audio input Mute status changed
    if (message.name == 'InputMuteStateChanged'):
        #print(f"inputName: {message.datain['inputName']} inputMuted: {message.datain['inputMuted']}")
        for x in MUTE_SWITCHES:
            if (x.mute_name == message.datain['inputName']):
                #print("boom")
                if (message.datain['inputMuted']):
                    x.publish_state(SwitchPayload.ON)
                else:
                    x.publish_state(SwitchPayload.OFF)     
    elif (message.name == 'InputVolumeChanged'):
        for x in VOLUME_SWITCHES:
            if (x.scene_name == message.datain['inputName']):
                x.publish_state(message.datain['inputVolumeDb'])
    elif (message.name == 'VirtualcamStateChanged'):
        if (message.datain['outputActive']): 
            VIRTUALCAM_SWITCH.publish_state(SwitchPayload.ON)
        else:
            VIRTUALCAM_SWITCH.publish_state(SwitchPayload.OFF)
    elif (message.name == 'RecordStateChanged'):
        if (message.datain['outputActive']): 
            RECORD_SWITCH.publish_state(SwitchPayload.ON)
        else:
            RECORD_SWITCH.publish_state(SwitchPayload.OFF)
    elif (message.name == 'StreamStateChanged'):
        if (message.datain['outputActive']): 
            STREAM_SWITCH.publish_state(SwitchPayload.ON)
        else:
            STREAM_SWITCH.publish_state(SwitchPayload.OFF)        

def on_switch(message):
    print("You changed the scene to {}".format(message.getSceneName()))


'''
try:
    scenes = ws.call(requests.GetSceneList())
    for s in scenes.getScenes():
        name = s['sceneName']
        print("Switching to {}".format(name))
        ws.call(requests.SetCurrentProgramScene(sceneName=name))
        time.sleep(2)
'''
def getAudioInputs(inputType):
    try:
        #scenes = ws.call(requests.GetInputList(inputKind="coreaudio_input_capture, sck_audio_capture"))
        scenes = ws.call(requests.GetInputList(inputKind=f"{inputType}"))
        for s in scenes.getInputs():
            name = s['inputName']
            if DEBUG: print("Audio Input Name: {}".format(name))
        #ws.call(requests.SetInputMute(inputName="AppleTV - Speakers",inputMuted=True))

    except KeyboardInterrupt:
        pass


class SwitchPayload(str, enum.Enum):
    OFF = "OFF"
    ON = "ON"

class SwitchType(str, enum.Enum):
    profile = "profile"
    record = "record"
    stream = "stream"
    virtualcam = "virtualcam"
    scene = "scene"
    mute_switch = "mute_switch"
    volume_level = "volume_level"

class Switch:
    """
    Represents a controllable aspect of OBS (Profile, Record, Stream, etc.)
    """
    def __init__(self):
        self.publish_config()
        self.subscribe()
        #self.publish_command(SwitchPayload.OFF)

    def publish_config(self):
        CLIENT.publish(self.config_topic, json.dumps(self.config))
        if DEBUG: print(f"Published config {self.config['name']}")
    
    def subscribe(self):
        CLIENT.subscribe(self.command_topic)
        if DEBUG: print(f"Subscribed to {self.config['name']}")
    
    def publish_state(self, payload):
        CLIENT.publish(self.state_topic, payload)
        if DEBUG: print(f"{self.config['name']} state changed to {payload}")
    
    def publish_command(self, payload):
        CLIENT.publish(self.command_topic, payload)
        if DEBUG: print(f"{self.config['name']} command published. Payload: {payload}")

class VirtualcamSwitch(Switch):
    def __init__(self,  mqtt_base_channel, mqtt_sensor_name):
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.virtualcam
        self.state_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/virtualcam/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/virtualcam/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}_virtualcam/config"
        #self.available_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/virtualcam/available"
        self.config = {
                "name": f"{self.mqtt_sensor_name} Virtual Camera",
                "unique_id": f"{self.mqtt_sensor_name}_virtualcam",
                "device": {
                    "name": f"{self.mqtt_sensor_name}",
                    "identifiers": f"[['mac',{MAC}]]",
                    "manufacturer": f"OBS Script v.{__version__}",
                    "sw_version": __version__
                },
                "state_topic": self.state_topic,
                "command_topic": self.command_topic,
                "payload_on": SwitchPayload.ON,
                "payload_off": SwitchPayload.OFF,
                #"availability": {
                #    "payload_available": SwitchPayload.ON,
                #    "payload_not_available": SwitchPayload.OFF,
                #    "topic": self.available_topic
                #},
                "icon": "mdi:webcam"
            }
        super().__init__()

class RecordSwitch(Switch):
    def __init__(self,  mqtt_base_channel, mqtt_sensor_name):
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.record
        self.state_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/record/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/record/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}_record/config"
        #self.available_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/virtualcam/available"
        self.config = {
                "name": f"{self.mqtt_sensor_name} record",
                "unique_id": f"{self.mqtt_sensor_name}_record",
                "device": {
                    "name": f"{self.mqtt_sensor_name}",
                    "identifiers": f"[['mac',{MAC}]]",
                    "manufacturer": f"OBS Script v.{__version__}",
                    "sw_version": __version__
                },
                "state_topic": self.state_topic,
                "command_topic": self.command_topic,
                "payload_on": SwitchPayload.ON,
                "payload_off": SwitchPayload.OFF,
                #"availability": {
                #    "payload_available": SwitchPayload.ON,
                #    "payload_not_available": SwitchPayload.OFF,
                #    "topic": self.available_topic
                #},
                "icon": "mdi:record-rec"
            }
        super().__init__()

class StreamSwitch(Switch):
    def __init__(self,  mqtt_base_channel, mqtt_sensor_name):
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.stream
        self.state_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/stream/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/stream/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}_stream/config"
        #self.available_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/virtualcam/available"
        self.config = {
                "name": f"{self.mqtt_sensor_name} stream",
                "unique_id": f"{self.mqtt_sensor_name}_stream",
                "device": {
                    "name": f"{self.mqtt_sensor_name}",
                    "identifiers": f"[['mac',{MAC}]]",
                    "manufacturer": f"OBS Script v.{__version__}",
                    "sw_version": __version__
                },
                "state_topic": self.state_topic,
                "command_topic": self.command_topic,
                "payload_on": SwitchPayload.ON,
                "payload_off": SwitchPayload.OFF,
                #"availability": {
                #    "payload_available": SwitchPayload.ON,
                #    "payload_not_available": SwitchPayload.OFF,
                #    "topic": self.available_topic
                #},
                "icon": "mdi:cloud-upload-outline"
            }
        super().__init__()

class sceneSwitches(Switch):
    def __init__(self, scene_name, mqtt_base_channel, mqtt_sensor_name):
        if DEBUG: print(f"***** Added Scene ")
        cleanName = scene_name.replace("-", "")
        cleanName = cleanName.replace(" ", "")
        self.scene_name = scene_name
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.scene
        self.state_topic = f"{self.mqtt_base_channel}/switch/{cleanName}/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{cleanName}/scene/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{cleanName}/config"
        self.config = {
                "name": f"Scene {self.scene_name}",
                "unique_id": f"{self.mqtt_sensor_name}_{cleanName}_scene",
                "device": {
                    "name": f"{self.mqtt_sensor_name}",
                    "identifiers": f"[['mac',{MAC}]]",
                    "manufacturer": f"BILL OBS Script v.{__version__}",
                    "sw_version": __version__
                },
                "state_topic": self.state_topic,
                "command_topic": self.command_topic,
                "icon": f"mdi:movie-open-play-outline",
                "payload_on": SwitchPayload.ON,
                "payload_off": SwitchPayload.OFF
            }
        super().__init__()

    def publish_remove_config(self):
        CLIENT.publish(self.config_topic, "")
        if DEBUG: print(f"Removed config {self.config['name']}")    

class muteSwitches(Switch):
    def __init__(self, mute_name, mqtt_base_channel, mqtt_sensor_name):
        if DEBUG: print(f"***** Added Scene ")
        cleanName = mute_name.replace("-", "")
        cleanName = cleanName.replace(" ", "")
        self.mute_name = mute_name
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.mute_switch
        self.state_topic = f"{self.mqtt_base_channel}/switch/{cleanName}/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{cleanName}/mute_switch/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{cleanName}/config"
        self.config = {
                "name": f"{self.mute_name}",
                "unique_id": f"{self.mqtt_sensor_name}_{cleanName}_scene",
                "device": {
                    "name": f"{self.mqtt_sensor_name}",
                    "identifiers": f"[['mac',{MAC}]]",
                    "manufacturer": f"BILL OBS Script v.{__version__}",
                    "sw_version": __version__
                },
                "state_topic": self.state_topic,
                "command_topic": self.command_topic,
                "icon": f"mdi:volume-low",
                "payload_on": SwitchPayload.ON,
                "payload_off": SwitchPayload.OFF
            }
        super().__init__()

    def publish_remove_config(self):
        CLIENT.publish(self.config_topic, "")
        if DEBUG: print(f"Removed config {self.config['name']}")    


class volumeControls(Switch):
    def __init__(self, scene_name, mqtt_base_channel, mqtt_sensor_name):
        if DEBUG: print(f"***** Added Number Switch ")
        cleanName = scene_name.replace("-", "")
        cleanName = cleanName.replace(" ", "")
        self.scene_name = scene_name
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.volume_level
        self.state_topic = f"{self.mqtt_base_channel}/number/{cleanName}/state"
        self.command_topic = f"{self.mqtt_base_channel}/number/{cleanName}/volume_level/set"
        self.config_topic = f"{self.mqtt_base_channel}/number/{cleanName}/config"
        self.config = {
                "name": f"{self.scene_name}",
                "unique_id": f"{self.mqtt_sensor_name}_{cleanName}_scene",
                "device": {
                    "name": f"{self.mqtt_sensor_name}",
                    "identifiers": f"[['mac',{MAC}]]",
                    "manufacturer": f"BILL OBS Script v.{__version__}",
                    "sw_version": __version__
                },
                "state_topic": self.state_topic,
                "command_topic": self.command_topic,
                "icon": f"mdi:knob",
                "min": "-100.0",
                "max": "0.0"
            }
        super().__init__()

    def publish_remove_config(self):
        CLIENT.publish(self.config_topic, "")
        if DEBUG: print(f"Removed config {self.config['name']}")    

def on_obs_connect():
    
    print("OBS Connection Successful")

def on_obs_disconnect():

    print("OBS has Disconnected")

# MQTT Event Functions
def on_mqtt_connect(client, userdata, flags, rc):
    """
    Called when the MQTT client is connected from the server.  Just prints a
    message indicating we connected successfully.
    """
    print("MQTT connection successful")
    
    #set_homeassistant_config()
    setup_basic_control_switches_in_homeassistant()
    setup_mute_switches_in_homeassistant("sck_audio_capture")
    setup_mute_switches_in_homeassistant("coreaudio_input_capture")	
    setup_volume_control_in_homeassistant("sck_audio_capture")
    setup_volume_control_in_homeassistant("coreaudio_input_capture")
    setup_scenes_in_homeassistant()

def on_mqtt_disconnect(client, userdata, rc):
    """
    Called when the MQTT client gets disconnected.  Just logs a message about it
    (we'll auto-reconnect inside of update_status()).
    """
    print("MQTT disconnected.  Reason: {}".format(str(rc)))

def on_mqtt_message(client, userdata, message):
    """
    Handles MQTT messages that have been subscribed to
    """
    payload = str(message.payload.decode("utf-8"))
    print(f"GOT THIS FROM HA: {message.topic}: {payload}")

    entity = message_to_switch_entity(message)
    if DEBUG: print(f"{message.topic}: {payload}")
    #print(f"########### this is the entity: {entity} and payload: {payload}")
    if entity != None:

        execute_action(entity, payload)
    
def virtualcam_started():
    """
    Publishes state of sensor and virtualcam switch
    """
    SENSOR.publish_state()
    SENSOR.publish_attributes()
    VIRTUALCAM_SWITCH.publish_state(SwitchPayload.ON)

def virtualcam_stopped():
    """
    Publishes state of sensor and virtualcam switch
    """
    SENSOR.publish_state()
    VIRTUALCAM_SWITCH.publish_state(SwitchPayload.OFF)

def message_to_switch_entity(message):
    """
    Converts MQTT Message to the corresponding switch entity
    """
    topic = pathlib.PurePosixPath(message.topic)
    message_type = SwitchType[topic.parent.stem] # Stream, Record, VirtualCam or Profile
    print(f"Recieved a messge of type: {message_type}")
    if message_type == SwitchType.stream:
        return STREAM_SWITCH
    if message_type == SwitchType.record:
        return RECORD_SWITCH
    if message_type == SwitchType.virtualcam:
        return VIRTUALCAM_SWITCH
    if message_type == SwitchType.volume_level:
        for volume_level in VOLUME_SWITCHES:
            if volume_level.command_topic == message.topic:
                return volume_level  
    if message_type == SwitchType.mute_switch:
        for mute in MUTE_SWITCHES:
            if mute.command_topic == message.topic:
                return mute  
    if message_type == SwitchType.profile:
        for profile in PROFILES:
            if profile.command_topic == message.topic:
                return profile
    if message_type == SwitchType.scene:
        for scene in SCENES:
            if scene.command_topic == message.topic:
                return scene
    return None


def setup_basic_control_switches_in_homeassistant():
    """
    Sets up profile, recording and streaming controls
    """
    global STREAM_SWITCH
    global RECORD_SWITCH
    global VIRTUALCAM_SWITCH
    # print("Setting up profiles and scenes for home assistant.")

    # Set up switches for autodiscovery
    STREAM_SWITCH = StreamSwitch(MQTT_BASE_CHANNEL, MQTT_SENSOR_NAME)
    RECORD_SWITCH = RecordSwitch(MQTT_BASE_CHANNEL, MQTT_SENSOR_NAME)
    VIRTUALCAM_SWITCH = VirtualcamSwitch(MQTT_BASE_CHANNEL, MQTT_SENSOR_NAME)
    checkVirtualCam = ws.call(requests.GetVirtualCamStatus())
    checkRecordStatus = ws.call(requests.GetRecordStatus())
    checkStreamStatus = ws.call(requests.GetRecordStatus())
    if (checkVirtualCam.datain['outputActive']): 
        VIRTUALCAM_SWITCH.publish_state(SwitchPayload.ON)
        #virtualcam_started()
    else:
        VIRTUALCAM_SWITCH.publish_state(SwitchPayload.OFF)
        #virtualcam_stopped()
    if (checkRecordStatus.datain['outputActive']): 
        RECORD_SWITCH.publish_state(SwitchPayload.ON)
        #virtualcam_started()
    else:
        RECORD_SWITCH.publish_state(SwitchPayload.OFF)
        #virtualcam_stopped()
    if (checkStreamStatus.datain['outputActive']): 
        STREAM_SWITCH.publish_state(SwitchPayload.ON)
        #virtualcam_started()
    else:
        STREAM_SWITCH.publish_state(SwitchPayload.OFF)
        #virtualcam_stopped()


def setup_mute_switches_in_homeassistant(inputType):

    #print(ws.call(requests.GetInputKindList()))


    if DEBUG: print("Setup Mute Switches in Home Assistant")
    global MUTE_SWITCH
    global MUTE_SWITCHES
    
		

    #scenes = ws.call(requests.GetInputList(inputKind="coreaudio_input_capture, sck_audio_capture"))
    scenes = ws.call(requests.GetInputList(inputKind=f"{inputType}"))
    
    #print(f"Result of Scenses: {scenes}")
    #MUTE_SWITCHES = []
    for s in scenes.getInputs():

        isMuted = ws.call(requests.GetInputMute(inputName=s["inputName"]))
        #print(f"########################## Mute Status is: {isMuted.datain['inputMuted']}")
       
        current_scene = isMuted.datain['inputMuted']

        name = s['inputName']

        if DEBUG: print(f"Setting up switch in HA called: {name}")
        mute_switch = muteSwitches(
            mute_name=name,
            mqtt_base_channel=MQTT_BASE_CHANNEL,
            mqtt_sensor_name=MQTT_SENSOR_NAME
        )
        MUTE_SWITCHES.append(mute_switch)
        if DEBUG: print(f"Scene {mute_switch.scene_name} added to SCENCES")

        if current_scene:
            MUTE_SWITCH = mute_switch
            mute_switch.publish_state(SwitchPayload.ON)
        else:
            mute_switch.publish_state(SwitchPayload.OFF)


def setup_scenes_in_homeassistant():
    """
    Publishes config, and subscribes to the command topic for each Scene.
    Also sets the current scene's state
    """
    #print("############## FIRST RUN setting up scenes")
    global SCENE
    global SCENES
    current_scene = ws.call(requests.GetCurrentProgramScene())
    scenes = ws.call(requests.GetSceneList(requestType="GetSceneList"))
    # x.publish_state(message.datain['inputVolumeDb'])
    SCENES = []
    for scene in scenes.datain['scenes']:
        name = scene['sceneName']
        #print(f"Setting up Scenes Switches in Home Assistant")
        scene_switch = sceneSwitches(
            scene_name=name,
            mqtt_base_channel=MQTT_BASE_CHANNEL,
            mqtt_sensor_name=MQTT_SENSOR_NAME
        )
        SCENES.append(scene_switch)
        if DEBUG: print(f"Scene {scene_switch.scene_name} added to SCENCES")
        if scene_switch.scene_name == current_scene.datain['currentProgramSceneName']:
            SCENE = scene_switch
            scene_switch.publish_state(SwitchPayload.ON)
        else:
            scene_switch.publish_state(SwitchPayload.OFF)

def setup_volume_control_in_homeassistant(inputType):

    global VOLUME_SWITCH
    global VOLUME_SWITCHES

    scenes = ws.call(requests.GetInputList(inputKind=f"{inputType}"))
    #scenes2 = ws.call(requests.GetInputList(inputKind="coreaudio_input_capture"))
    		
    #print(scenes)

    #VOLUME_SWITCHES = []
    for s in scenes.getInputs():
        name = s['inputName']
        volumeLevel = ws.call(requests.GetInputVolume(inputName=s["inputName"]))
        volumeLevel = volumeLevel.datain['inputVolumeDb']
        volume_switch = volumeControls(
            scene_name= name,
            mqtt_base_channel=MQTT_BASE_CHANNEL,
            mqtt_sensor_name=MQTT_SENSOR_NAME
        )
        VOLUME_SWITCH = volume_switch
        VOLUME_SWITCHES.append(volume_switch)    
        volume_switch.publish_state(volumeLevel)


def script_update():
    """
    Applies any changes made to the MQTT settings in the OBS Scripts GUI then
    reconnects the MQTT client.
    """

    #print(f"It all starts here with MAC: {MAC}")

    # Apply the new settings
    global MQTT_HOST
    global MQTT_USER
    global MQTT_PW
    global MQTT_PORT
    global MQTT_BASE_CHANNEL
    global MQTT_SENSOR_NAME
    global INTERVAL
    global CONTROL
    global DEBUG
    mqtt_host = MQTT_HOST

    mqtt_user = MQTT_USER

    mqtt_pw = MQTT_PW

    mqtt_base_channel = MQTT_BASE_CHANNEL

    mqtt_sensor_name = MQTT_SENSOR_NAME

    mqtt_port = MQTT_PORT


    #INTERVAL = obs.obs_data_get_int(settings, "interval")
    #CONTROL = obs.obs_data_get_bool(settings, "controllable")
    #DEBUG = obs.obs_data_get_bool(settings, "debug")

    # Disconnect (if connected) and reconnect the MQTT client
    #CLIENT.disconnect()
    try:
        if MQTT_PW != "" and MQTT_USER != "":
            CLIENT.username_pw_set(MQTT_USER, password=MQTT_PW)
        CLIENT.connect_async(MQTT_HOST, MQTT_PORT, 60)
        #print("MQTT Client Connected")
    except (socket.gaierror, ConnectionRefusedError) as e:
        print("NOTE: Got a socket issue: %s" % e)
        pass # Ignore it for now

   
    # obs.obs_frontend_remove_event_callback(frontend_changed)
    # obs.obs_frontend_add_event_callback(frontend_changed)
    # Remove and replace the timer that publishes our status information
    # obs.timer_remove(update_status)
    # obs.timer_add(update_status, INTERVAL * 1000)

    #set_homeassistant_config()

    CLIENT.loop_forever()


def execute_action(switch, payload):

    if switch.switch_type == SwitchType.mute_switch:
        if payload == SwitchPayload.ON:
            if DEBUG: print(f"Action for switch: {switch.mute_name} with a payload of: {payload}")
            ws.call(requests.SetInputMute(inputName=switch.mute_name,inputMuted=True))

        else:
            if DEBUG: print(f"Action for switch: {switch.mute_name} with a payload of: {payload}")
            ws.call(requests.SetInputMute(inputName=switch.mute_name,inputMuted=False))

    if switch.switch_type == SwitchType.volume_level:
        if DEBUG: print(f"Action for switch: {switch.scene_name} with a payload of: {payload}")
        result = ws.call(requests.SetInputVolume(inputName=switch.scene_name,inputVolumeDb=int(payload)))

    if switch.switch_type == SwitchType.virtualcam:
        if payload == SwitchPayload.ON:
            ws.call(requests.StartVirtualCam())
        else:
            ws.call(requests.StopVirtualCam())    

    if switch.switch_type == SwitchType.record:
        if payload == SwitchPayload.ON:
            ws.call(requests.StartRecord())
        else:
            ws.call(requests.StopRecord())   

    if switch.switch_type == SwitchType.stream:
        if payload == SwitchPayload.ON:
            ws.call(requests.StartStream())
        else:
            ws.call(requests.StopStream())  
    if switch.switch_type == SwitchType.scene:
        for scene in SCENES:
            name = scene.scene_name
            if name == switch.scene_name:
                ws.call(requests.SetCurrentProgramScene(sceneName=switch.scene_name))
                scene.publish_state(SwitchPayload.ON)
            else:
                scene.publish_state(SwitchPayload.OFF)

def test(event):
    print(f"test: {event}")





# Using a global MQTT client variable to keep things simple:
CLIENT = mqtt.Client()
CLIENT.on_connect = on_mqtt_connect
CLIENT.on_disconnect = on_mqtt_disconnect
CLIENT.on_message = on_mqtt_message

ws = obsws(host, port, password, authreconnect=authreconnect, on_connect=on_obs_connect())
ws.register(on_event)
ws.register(on_switch, events.SwitchScenes)
ws.register(on_switch, events.CurrentProgramSceneChanged)
ws.register(test, events.InputVolumeMeters)
#ws.on_connect = on_obs_connect()
#ws.on_disconnect = on_obs_disconnect()
ws.connect()

#on_obs_connect()
script_update()
'''getAudioInputs()
ws.disconnect()'''
