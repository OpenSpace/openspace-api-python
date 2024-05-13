import socket
from threading import Thread
import asyncio

class SocketWrapper:
    def __init__(self, address: str, port: int):
        self._address = address
        self._port = port
        self._client = None
        self._onConnect = lambda: None
        self._onDisconnect = lambda: None
        self._onMessage = lambda message: None
        self._inBuffer = ''
        self._disconnecting = False

    def onConnect(self, callback):
        self._onConnect = callback

    def onDisconnect(self, callback):
        self._onDisconnect = callback

    def onMessage(self, callback):
        self._onMessage = callback

    async def _handle_receive(self):
        while True:
            try:
                data = await self._loop.sock_recv(self._client, 1024)
                if data:
                    self._inBuffer += data.decode()
                    while '\n' in self._inBuffer:
                        message, self._inBuffer = self._inBuffer.split('\n', 1)
                        try:
                            self._onMessage(message)
                        except asyncio.InvalidStateError:
                            print("Did not close topic after use. Either use "
                                  "`async for foo in topic.iterator()` to continue "
                                  "recieving callbacks or call topic.cancel() to close "
                                  "the topic")
                else:
                    print("Error receiving data from OpenSpace. Connection closed.")
                    break
            except OSError as e:
                print(f"Connection exited with: {e}")
                break

        self.disconnect()

    def connect(self):
        self._client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._client.connect((self._address, self._port))
            self._disconnecting = False
            self._loop = asyncio.get_event_loop()
            asyncio.create_task(self._handle_receive(), name="Handle receive")
            asyncio.create_task(self._onConnect(), name="On connect")
        except ConnectionRefusedError as e:
            print(f"Could not connect to {self._address}:{self._port}. Is OpenSpace running?")
            print(f"Error code: {e}")
            self.disconnect()


    async def send(self, message):
        await self._loop.sock_sendall(self._client, (message + "\n").encode())

    def send(self, message):
        self._client.sendall((message + "\n").encode())

    def disconnect(self):
        if self._disconnecting:
             return

        self._disconnecting = True
        self._onDisconnect()
        self._client.close()