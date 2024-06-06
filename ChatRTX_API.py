import requests
import random
import string
import psutil
import json
import os
import socket
import time
from threading import Thread
from multiprocessing import Queue

port = None
cookie = None

appdata_folder = os.path.dirname(os.getenv('APPDATA')).replace('\\', '/')
cert_path = appdata_folder + "/Local/NVIDIA/ChatRTX/RAG/trt-llm-rag-windows-ChatRTX_0.3/certs/servercert.pem"
key_path =  appdata_folder + "/Local/NVIDIA/ChatRTX/RAG/trt-llm-rag-windows-ChatRTX_0.3/certs/serverkey.pem"
ca_bundle = appdata_folder + "/Local/NVIDIA/ChatRTX/env_nvd_rag/Library/ssl/cacert.pem"
print(cert_path)
print(key_path)
print(ca_bundle)
print()

def find_ChatRTX_port():
    global port
    connections = psutil.net_connections(kind='inet')
    for host in connections:
        try:
            if not host.pid:
                continue
            process = psutil.Process(host.pid)

            if "ChatRTX\\env_nvd_rag\\python.exe" in process.exe():
                test_port = host.laddr.port
                url = f"https://127.0.0.1:{test_port}/queue/join"
                response = requests.post(url, data="", timeout=0.1, cert=(cert_path, key_path), verify=ca_bundle)
                if response.status_code == 422:
                    port = test_port
                    return
        except Exception as e:
            pass

def get_ChatRTX_cookie():
    global cookie
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port + 1))
        cookie = str(sock.recv(99, ), "latin-1")
        sock.close()
    except:
        pass

def listen_for_updates(session_hash, message):
    url = f"https://127.0.0.1:{port}/queue/data?session_hash={session_hash}"
    response = requests.get(url, stream=True, cert=(cert_path, key_path), verify=ca_bundle, cookies={"_s_chat_":cookie})
    for line in response.iter_lines():
        if not line:
            continue
        data = json.loads(line[6:])
        if data['msg'] == 'process_completed':
            try:
                if data['output']['data'][0][0][0] == message and data['output']['data'][0][0][1] != None:
                    return data['output']['data'][0][0][1]
                # return 1
                else:
                    return session_hash
            except: pass
    return session_hash

def cycle(session_hash, jsonReq, message, queue):
    """
    Sends a request and then waits for the server to respond using the data in jsonReq
    """
    statusList = ["Starting Connection", "Checking Connection", "Starting Link", "Sending Prompt", "Starting Response", "Generating Response", "Closing Connection"]
    status = statusList[jsonReq["fn_index"] - 81]
    queue.put(("status", status))

    url = f"https://127.0.0.1:{port}/queue/join"
    json_string = json.dumps(jsonReq)

    requests.post(url, data=json_string, cert=(cert_path, key_path), verify=ca_bundle, cookies={"_s_chat_":cookie})
    response = listen_for_updates(session_hash, message)
    jsonReq["fn_index"] = jsonReq["fn_index"] + 1
    return response

def send_message_sync(message, queue):
    if message == "":
        queue.put(("error", "ChatRTX cannot process a blank request"))
        return
    
    session_hash = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    jsonReq = {
        "data": [],
        "event_data": None,
        "fn_index": 81,
        "session_hash": session_hash,
        "trigger_id": 113
    }
    
    # Starting up the connection with ChatRTX
    for _ in range(3):
        cycle(session_hash, jsonReq, message, queue)

    # Sending ChatRTX the prompt
    jsonReq["data"] = [message, [], "Folder Path", "Mistral 7B int4", None]
    cycle(session_hash, jsonReq, message, queue)

    # Waiting for it to process
    jsonReq["data"] = [message, []]
    cycle(session_hash, jsonReq, message, queue)

    # Receiving data back from chatRTX
    jsonReq["data"] = [[[message, None]], None]
    response = cycle(session_hash, jsonReq, message, queue)

    # Closing the session with chatRTX (or something)
    jsonReq["data"] = []
    cycle(session_hash, jsonReq, message, queue)

    print(" " * 19, end="\r")

    if response == session_hash:
        queue.put(("error", "No data could be received from the AI"))
    else:
        queue.put(("response", response))


# The 2 functions that are called on by the user
def send_msg(message):
    """
    Send a message to chat rtx to process.
    Args: message
    Returns: Object to be passed to read_status() from time to time
    """
    
    result_queue = Queue()
    thread = Thread(target=send_message_sync, args=[message, result_queue])
    thread.start()
    return result_queue

def read_status(obj):
    """
    Checks if anything has changed, and returns the status message if it has, otherwise None
    Args: obj

    obj is the object that is returned by send_msg()
    Returns: status or None
    """
    if not obj.empty():
        return obj.get()
    

# Init stuffs
print("Finding 'Chat with RTX' server port...")
find_ChatRTX_port()
if not port:
    print("Failed to find port. Retrying... (If this script is being run on startup, this message is normal)")
    for i in range(60):
        time.sleep(0.75)
        find_ChatRTX_port()
        if port:
            break
        print(f"Failed to find port. Retrying ({i + 1}/60)", end="\r")
    print("\n")
if not port:
    raise AttributeError(
        "Failed to find a server port for 'Chat with RTX'. Ensure the server is running."
    )
print(f"Server port found on\033[96m port {port}\33[0m")
print("Getting 'Chat with RTX' authorization cookie...")
get_ChatRTX_cookie()
if not cookie:
    raise AttributeError(
        "Failed to get cookie for 'Chat with RTX'. Ensure that 'Chat with RTX' was run using our modified loader."
    )
print(f"Authorization cookie found: \033[32m{cookie}\033[0m")
print("Initialization complete, returning to program...\n")
