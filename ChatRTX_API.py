"""# Chat with RTX API

An API to mesh with 'Chat with RTX', and AI model made by NVIDIA.

IMPORTANT: This API will work ONLY if Chat with RTX was run with ChatRTX_Runner, our modified bootloader.
"""

import requests
import random
import string
import psutil
import json
import os
import socket
import time
import typing
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

def _find_ChatRTX_port():
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

def _get_ChatRTX_cookie():
    global cookie
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port + 1))
        cookie = str(sock.recv(99, ), "latin-1")
        sock.close()
    except:
        pass

def _listen_for_updates(session_hash, message):
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
                else:
                    return session_hash
            except: pass
    return session_hash

def _cycle(session_hash, jsonReq, message, queue):
    """
    Sends a request and then waits for the server to respond using the data in jsonReq
    """
    statusList = ["Starting Connection", "Checking Connection", "Starting Link", "Sending Prompt", "Starting Response", "Generating Response", "Closing Connection"]
    status = statusList[jsonReq["fn_index"] - 81]
    queue.put(("status", status))

    url = f"https://127.0.0.1:{port}/queue/join"
    json_string = json.dumps(jsonReq)

    requests.post(url, data=json_string, cert=(cert_path, key_path), verify=ca_bundle, cookies={"_s_chat_":cookie})
    response = _listen_for_updates(session_hash, message)
    jsonReq["fn_index"] = jsonReq["fn_index"] + 1
    return response

def _send_message_sync(message, contextList, queue):
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
        _cycle(session_hash, jsonReq, message, queue)

    # Sending ChatRTX the prompt
    jsonReq["data"] = [message, contextList, "Folder Path", "Mistral 7B int4", None]
    _cycle(session_hash, jsonReq, message, queue)

    # Waiting for it to process
    jsonReq["data"] = [message, contextList]
    _cycle(session_hash, jsonReq, message, queue)

    # Receiving data back from chatRTX
    contextList.append([message, None])
    jsonReq["data"] = [contextList, None]
    response = _cycle(session_hash, jsonReq, message, queue)

    # Closing the session with chatRTX (or something)
    jsonReq["data"] = []
    _cycle(session_hash, jsonReq, message, queue)

    if response == session_hash:
        queue.put(("error", "No data could be received from the AI"))
    else:
        queue.put(("response", response))


# ================================================
# The 2 functions that are called on by the user

def send_msg(message: str, context: dict = {}) -> Queue:
    """Send a message to chat rtx to process.

    $$ Context currently doesn't work, as even though their website adds that metadata, it's never called upon $$

    Args: 
        message: The message to sent to the AI
        context: Context from previous AI prompts and responses

    Returns:
        Object to be passed to read_status() from time to time

    Context is a dictionary, with the the key being the user prompt, and the value being the AI response
    """

    contextList = []
    for i in context:
        contextList.append(list(i))
    
    result_queue = Queue()
    thread = Thread(target=_send_message_sync, args=[message, contextList, result_queue])
    thread.start()
    return result_queue

def read_status(obj: object) -> typing.Optional[tuple]:
    """Checks if anything has changed, and returns the status message if it has, otherwise None

    Args: 
        obj: object that is returned by send_msg()
    Returns: 
        status(tuple) or None
    """
    if not obj.empty():
        return obj.get()
    return None

# =========================
# Init stuffs

print("Finding 'Chat with RTX' server port...")
_find_ChatRTX_port()
if not port:
    print("Failed to find port. Retrying... (If this script is being run on startup, this message is normal)")
    for i in range(60):
        time.sleep(0.75)
        _find_ChatRTX_port()
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
_get_ChatRTX_cookie()
if not cookie:
    raise AttributeError(
        "Failed to get cookie for 'Chat with RTX'. Ensure that 'Chat with RTX' was run using our modified loader."
    )
print(f"Authorization cookie found: \033[32m{cookie}\033[0m")
print("Initialization complete, returning to program...\n")
