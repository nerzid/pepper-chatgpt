from __future__ import print_function
from Tkinter import *
from PIL import Image, ImageTk
import cv2
import ttk
import numpy as np
import qi
import requests
import json

PEPPER_IP = ''
PEPPER_PORT = 9559

CHATGPT_API_ENDPOINT = ''
CHATGPT_API_KEY = ''

GUI_ROOT = None
QI_SESSION = None
connection_status = 'Not Connected'
connect_button = None
video_client = None
video_label = None # this is where we show the video
video_frame = None

def connect_robot():
    global QI_SESSION

    if QI_SESSION is not None and QI_SESSION.isConnected():
        # connect btn has been pressed while robot was already connect --> it is the disconnedt btn...
        del QI_SESSION

        QI_SESSION = qi.Session()  # we make a new sess but don't connect it to anything --> essentially disconnect
        print("disconnecting interface by terminating session.")

        try:
            global SpeechRecognition
            SpeechRecognition.stop()
            del SpeechRecognition
        except (RuntimeError, NameError):
            # when camera tab is not open
            pass

    else:
        print("connecting interface to new robot session")

        # normal connect, we make a new session and connect to it
        try:
            # TODO doesn't solve the problem that session might still be trying to connect to invalid IP...
            print("attempting close and del session")
            QI_SESSION.close()
            del QI_SESSION
            time.sleep(1)
        except AttributeError:
            print("close attribute excaption pass...")
            # if the prev session is still trying to connect...
            pass

        QI_SESSION = None
        QI_SESSION = qi.Session()
        try:


            QI_SESSION.connect(str("tcp://" + str(PEPPER_IP) + ":" + str(PEPPER_PORT)))
            change_connection_status('Connected!')
            change_connect_button_label('Disconnect')
        except RuntimeError as msg:
            print("qi session connect error!:")
            change_connection_status('Error: ' + str(msg))

            QI_SESSION = None
            raise Exception("Couldn't connect session")
        get_all_services()
        update_video_stream()

def disconnect():
    global QI_SESSION, video_label, video_frame
    if QI_SESSION is None:
        return
    try:
        QI_SESSION.close()
        del QI_SESSION
        change_connection_status('Disconnected')
        video_label.config(image=None)
        video_label.image = None
        change_connect_button_label('Connect')
        print('Disconnected')
    except AttributeError:
        print('disconnect failed')
        change_connection_status('Disconnect failed!')

    QI_SESSION = None
    
def disconnect_and_close_window():
    disconnect()
    GUI_ROOT.destroy()

def build_gui():
    # Create the main application window
    global GUI_ROOT
    root = Tk()
    root.title("Pepper Controller")
    root.protocol("WM_DELETE_WINDOW", disconnect_and_close_window)
    GUI_ROOT = root

    # Create a frame to contain all widgets
    frame = ttk.Frame(root, padding="10 10 10 10")
    frame.grid(row=0, column=0, sticky=(W, E, N, S))

    # Make the frame and the main window responsive
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(
        1, weight=3
    )  # More weight to the second column to stretch the textboxes

    # Pepper IP
    ip_label = ttk.Label(frame, text="Pepper IP:")
    ip_label.grid(row=0, column=0, sticky=W, pady=5)

    ip_entry = ttk.Entry(frame)
    ip_entry.grid(row=0, column=1, sticky=(W, E), pady=5)
    ip_entry.insert(0, PEPPER_IP)
    ip_entry.bind("<KeyRelease>", on_pepper_ip_change)

    # Connection Status
    status_label = ttk.Label(frame, text="Connection Status:")
    status_label.grid(row=1, column=0, sticky=W, pady=5)

    global connection_status
    connection_status = ttk.Label(frame, text="Not connected")
    connection_status.grid(row=1, column=1, sticky=(W, E), pady=5)

    global connect_button
    # Connect Button
    connect_button = ttk.Button(frame, text="Connect to Pepper", command=connect_robot)
    connect_button.grid(row=2, columnspan=2, pady=10)

    chatgpt_api_endpoint_label = ttk.Label(frame, text="ChatGPT API Endpoint:")
    chatgpt_api_endpoint_label.grid(row=3, column=0, sticky=W, pady=5)

    chatgpt_api_endpoint_entry = ttk.Entry(frame)
    chatgpt_api_endpoint_entry.grid(row=3, column=1, sticky=(W, E), pady=5)

    chatgpt_api_key_label = ttk.Label(frame, text="ChatGPT API Key:")
    chatgpt_api_key_label.grid(row=4, column=0, sticky=W, pady=5)

    chatgpt_api_key_entry = ttk.Entry(frame)
    chatgpt_api_key_entry.grid(row=4, column=1, sticky=(W, E), pady=5)
    
    # Test ChatGPT Button
    test_chatgpt_button = ttk.Button(frame, text="Test ChatGPT Connection")
    test_chatgpt_button.grid(row=5, columnspan=2, pady=10)

    take_then_send_photo_to_chatgpt_button = ttk.Button(frame, text="Take then Send Photo to ChatGPT", command=take_then_send_photo_to_chatgpt)
    take_then_send_photo_to_chatgpt_button.grid(row=6, columnspan=2, pady=10)

    # Message
    message_label = ttk.Label(frame, text="Message:")
    message_label.grid(row=7, column=0, sticky=W, pady=5)

    global message_entry
    message_entry = ttk.Entry(frame)
    message_entry.grid(row=7, column=1, sticky=(W, E), pady=5)
    

    # Send Message Button
    send_button = ttk.Button(frame, text="Send Message to Pepper", command=send_text_to_pepper)
    send_button.grid(row=8, columnspan=2, pady=10)
    
    global video_frame
    # Create a frame for the video
    video_frame = ttk.Frame(root, padding="10 10 10 10")
    video_frame.grid(row=1, column=0, sticky=(W, E, N, S))

    # Make the video frame responsive
    video_frame.columnconfigure(0, weight=1)

    global video_label
    video_label = ttk.Label(video_frame, text="Video Stream")
    video_label.pack()
    
    return root

def on_pepper_ip_change(event):
    global PEPPER_IP
    PEPPER_IP = event.widget.get()

def change_connection_status(new_status):
    connection_status.config(text=new_status)

def change_connect_button_label(new_label):
    if new_label == 'Disconnect':
        connect_button.config(command=disconnect)
    else:
        connect_button.config(command=connect_robot)
    connect_button.config(text=new_label)

def update_camera_view():
    # see if there are any old video subscribers...
    try:
        if video_srv.getSubscribers():
            for subscriber in video_srv.getSubscribers():
                if "CameraStream" in subscriber:  # name passed as argument on subscription
                    video_srv.unsubscribe(subscriber)

    except (NameError, RuntimeError):
        # happens when camera tab is open when there is no server has been restarted?
        return render_template("camera.html")


    resolution = vision_definitions.kQVGA  # 320 * 240
    colorSpace = vision_definitions.kRGBColorSpace
    global imgClient
    imgClient = video_srv.subscribe("CameraStream", resolution, colorSpace, 30)

    global camera_tab_closed
    camera_tab_closed = False

    global camera_tab_timestamp
    camera_tab_timestamp = timer()

    global SpeechRecognition
    SpeechRecognition = SpeechRecognitionModule("SpeechRecognition", ip, port)
    SpeechRecognition.start()

    return render_template("camera.html")

def get_all_services():
    """
    Provides global references to all naoqi services used somewhere down the line
    """
    global tts_srv
    tts_srv = QI_SESSION.service("ALTextToSpeech")

    global al_srv
    al_srv = QI_SESSION.service("ALAutonomousLife")

    global ba_srv
    ba_srv = QI_SESSION.service("ALBasicAwareness")

    global ab_srv
    ab_srv = QI_SESSION.service("ALAutonomousBlinking")

    global motion_srv
    motion_srv = QI_SESSION.service("ALMotion")

    global video_srv
    video_srv = QI_SESSION.service("ALVideoDevice")
    
    global video_client
    video_client = video_srv.subscribeCamera(
        "python_client", 0, 2, 13, 30  # Camera index 0, resolution 2 (640x480), color space 11 (BGR), 30 fps
    )    
    
    global tablet_srv
    tablet_srv = QI_SESSION.service("ALTabletService")

    global as_srv
    as_srv = QI_SESSION.service("ALAnimatedSpeech")

    global ap_srv
    ap_srv = QI_SESSION.service("ALAnimationPlayer")

    global posture_srv
    posture_srv = QI_SESSION.service("ALRobotPosture")

    global ar_srv
    ar_srv = QI_SESSION.service("ALAudioRecorder")

    global ad_srv
    ad_srv = QI_SESSION.service("ALAudioDevice")

    global fd_srv
    fd_srv = QI_SESSION.service("ALFaceDetection")

    global mem_srv
    mem_srv = QI_SESSION.service("ALMemory")

    global lm_srv
    lm_srv = QI_SESSION.service("ALListeningMovement")

    global sm_srv
    sm_srv = QI_SESSION.service("ALSpeakingMovement")

    global audio_player
    audio_player = QI_SESSION.service("ALAudioPlayer")

    global led_srv
    led_srv = QI_SESSION.service("ALLeds")

def send_text_to_pepper():
    global tts_srv, message_entry
    tts_srv.say(message_entry.get())
    
def take_then_send_photo_to_chatgpt():
    pass
    
def send_message_to_chatgpt(message):
        # Make a POST request to the API endpoint
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + CHATGPT_API_KEY
    }
    data = {
        "prompt": message,
        "max_tokens": 150,  # Adjust the max tokens as needed
        "temperature": 0.7,  # Adjust the temperature as needed
        "stop": ["\n"]  # Stop generating text at newline character
    }
    response = requests.post(CHATGPT_API_ENDPOINT, headers=headers, data=json.dumps(data))
    
    # Check if the request was successful
    if response.status_code == 200:
        return response.json()["choices"][0]["text"].strip()
    else:
        print("Error:", response.text)
        return None
    
def update_video_stream():
    if QI_SESSION is None:
        return
    if not QI_SESSION.isConnected():
        return
    # Retrieve an image from Pepper
    pepper_frame = video_srv.getImageRemote(video_client)
    
    if pepper_frame is not None:
    
        # Extract image data and convert to a numpy array
        width = pepper_frame[0]
        height = pepper_frame[1]
        array = pepper_frame[6]
        image = np.frombuffer(array, dtype=np.uint8).reshape((height, width, 3))

        # Convert the image to a format suitable for Tkinter
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(image)
        image = ImageTk.PhotoImage(image)

        # Update the label with the new image
        video_label.config(image=image)
        video_label.image = image

    # Schedule the next update
    GUI_ROOT.after(100, update_video_stream)  # ~30 fps


if __name__ == "__main__":
    gui = build_gui()
    gui.mainloop()
    