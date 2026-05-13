import asyncio
import socket
from traceback import print_exc
from typing import Callable, Coroutine, Any

class SocketWrapper:
  """
  TCP socket for OpenSpace API communication.

  :param address: The hostname or IP address of the OpenSpace instance to connect to.
  :param port: The port OpenSpace is listening on (4681 by default).
  """

  def __init__(self, address: str, port: int):
    # Ipv6 addresses are resolved to '::1' in Windows which causes issues with
    # `asyncio.sock_connect`, changing it to an Ipv4 address fixes the issue
    if(address.lower() == 'localhost'):
        address = '127.0.0.1'
    self._address = address
    self._port = port
    self._client: socket.socket | None = None
    self._loop: asyncio.AbstractEventLoop | None = None
    self._onConnect: Callable[[], Coroutine[Any, Any, None]] = self._noOpAsync
    self._onDisconnect: Callable[[], None] = lambda: None
    self._onMessage: Callable[[str], None] = lambda message: None
    self._inBuffer: str = ''
    self._isDisconnecting: bool = False

  async def _noOpAsync(self) -> None:
    pass

  def onConnect(self, callback: Callable[[], Coroutine[Any, Any, None]]) -> None:
    self._onConnect = callback

  def onDisconnect(self, callback: Callable[[], None]) -> None:
    self._onDisconnect = callback

  def onMessage(self, callback: Callable[[str], None]) -> None:
    self._onMessage = callback

  async def _handleReceive(self) -> None:
    if self._client is None:
      print("Error: Cannot receive data, not connected to OpenSpace.")
      return
    if self._loop is None:
      print("Error: Cannot receive data, event loop not found.")
      return

    while True:
      try:
        data = await self._loop.sock_recv(self._client, 1024)
        if data:
          self._inBuffer += data.decode()
          while "\n" in self._inBuffer:
            message, self._inBuffer = self._inBuffer.split("\n", 1)
            try:
              self._onMessage(message)
            except Exception as e:
              print(f"Error receiving data: {type(e)}: {e}")
              print_exc()
        else:
          print("Error receiving data from OpenSpace. Connection closed.")
          break
      except ConnectionAbortedError as e:
        if not self._isDisconnecting:
          print(f"Connection aborted: {e}")
        break
      except OSError as e:
        print(f"Connection error: {e}")
        print_exc()
        break
      except Exception as e:
        print(f"Unexpected error: {type(e)}: {e}")
        print_exc()
        break
    self.disconnect()

  async def connect(self) -> None:
    """Connect to OpenSpace"""
    self._client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._client.setblocking(False)
    self._loop = asyncio.get_running_loop()
    try:
      await self._loop.sock_connect(self._client, (self._address, self._port))
      self._isDisconnecting = False
      asyncio.create_task(self._handleReceive(), name="Handle receive")
      await self._onConnect()
    except ConnectionRefusedError as e:
      print(f"Could not connect to {self._address}:{self._port}. Is OpenSpace running?")
      print(f"Error code: {e}")
      self.disconnect()

  def send(self, message: str) -> None:
    """
    Send a message to OpenSpace.

    :param message: The message string to send.
    :raises `RuntimeError`: If the socket is not connected.
    """
    if self._client is None:
      raise RuntimeError("Cannot send: socket is not connected")
    self._client.sendall((message + "\n").encode())

  def disconnect(self):
    """Disconnect from OpenSpace."""
    if self._isDisconnecting:
      return

    self._isDisconnecting = True
    self._onDisconnect()
    if self._client is not None:
      self._client.close()
      self._client = None
