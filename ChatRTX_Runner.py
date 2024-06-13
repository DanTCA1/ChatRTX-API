import subprocess
import time
import traceback
import socket
import selectors
import types
import os
from pyautogui import hotkey

try:
    appdata_folder = os.path.dirname(os.getenv('APPDATA')).replace('\\', '/')
    chatRTX_path = appdata_folder + "/Local/NVIDIA/ChatRTX/RAG/trt-llm-rag-windows-ChatRTX_0.3/"
    keyword = "in browser to start ChatRTX"

    print("\n\nStarting ChatRTX...\n\nAny errors you see following this message don't matter.\033[2m")

    process = subprocess.Popen([chatRTX_path + "app_launch.bat"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, shell=True, cwd=chatRTX_path)

    while True:
        time.sleep(0.1)
        line = process.stdout.readline().decode("utf-8").strip()

        if keyword.lower() in line.lower():
            output = line
            break

    output = output.split("127.0.0.1:", 1)[1]
    port, output = output.split("?cookie=", 1)
    port = int(port) + 1
    cookie = output.split("&", 1)[0]
    print(f"\033[22m\nStarting cookie supply server on port \033[96m{port}\33[0m with cookie \033[32m{cookie}\033[0m\n")
    time.sleep(0.1)
    hotkey("ctrl", "w")
    hotkey("alt", "tab")

    lSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sel = selectors.DefaultSelector()
    cookieCount = 0
    try:
        lSock.bind(("", port))
    except OSError:
        raise OSError(
            f"Could not start cookie supply server on port {port} because that port is already being used"
        ) from None
    lSock.listen()
    sel.register(lSock, selectors.EVENT_READ, data=None)

    while True:
        events = sel.select(timeout=0.5)
        buffer = ["-", "\\", "|", "/"][round(time.time()//0.5 % 4)]
        print(f"The server is running [{buffer}] and has served {cookieCount} cookie(s) so far", end="\r")
        if not events:
            continue
        for key, mask in events:
            if key.data is None:
                conn, addr = key.fileobj.accept()
                conn.setblocking(False)
                data = types.SimpleNamespace(sent=False)
                events = selectors.EVENT_WRITE
                sel.register(conn, events, data=data)

            else:
                if mask & selectors.EVENT_WRITE:
                    if key.data.sent == False:
                        cookieCount += 1
                        key.fileobj.send(bytes(cookie, "latin-1"))
                        key.data.sent = True


except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting... (This may take a while)")
except Exception as error:
    print("An error has occurred, and the server will now shut down. Error:\033[0;3;31m")
    traceback.print_exception(error)
    print("\033[0m", end="")
finally:
    sel.close()
    process.communicate(input=b"\x03")
    exit(0)