import asyncio
import socket
from threading import Thread
from traceback import print_exc

class SocketWrapper:
    def __init__(self, address: str, port: int):

        # Ipv6 addresses are resolved to '::1' in Windows which causes issues with
        # `asyncio.sock_connect`, changing it to an Ipv4 address fixes the issue
        if(address.lower() == 'localhost'):
            address = '127.0.0.1'
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
                        except Exception as e:
                            print(f"Error receiving data: {type(e)}: {e}")
                            print_exc()
                else:
                    print("Error receiving data from OpenSpace. Connection closed.")
                    break
            except ConnectionAbortedError as e:
                print(f"Connection exited with: {e}")
                break
            except OSError as e:
                print(f"Connection exited with: {e}")
                print_exc()
                break
        self.disconnect()

    async def connect(self):
        self._client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._client.setblocking(False)
        self._loop = asyncio.get_event_loop()
        try:
            await self._loop.sock_connect(self._client, (self._address, self._port))
            self._disconnecting = False
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