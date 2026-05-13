import asyncio
import json
from .topic import Topic
from .socketwrapper import SocketWrapper
from collections import namedtuple
from functools import partial
from traceback import print_exc
from typing import Any, AsyncGenerator, Callable, Coroutine, NamedTuple

def toNamedTuple(content: dict, name: str = "namedtuple") -> NamedTuple:
  """Recursively converts a `dictionary` to a `namedtuple`."""

  T = namedtuple(name, content.keys())
  values = []
  for k, v in content.items():
    if isinstance(v, dict):
      values.append(toNamedTuple(v, k))
    else:
      values.append(v)

  return T(*values)

ApiVersion = {
  "type": "apiHandshake",
  "apiVersion": {
    "major": 1,
    "minor": 0,
    "patch": 0
  }
}

class Api:
  """
  Construct an instance of the OpenSpace API.

  :param address: The hostname or IP address of the OpenSpace instance to connect to.
  :param port: The port OpenSpace is listening on (4681 by default).
  """

  def __init__(self, address: str, port: int):
    self._callbacks: dict[int, Callable[[Any], None]] = {}
    self._topicCancelEvents: dict[int, asyncio.Event] = {}
    self._nextTopicId: int = 0
    self._userOnConnect: Callable[[], Coroutine[Any, Any, None]] | None = None
    self._userOnDisconnect: Callable[[], None] | None = None

    socket = SocketWrapper(address, port)
    socket.onConnect(self.__onConnect)
    socket.onDisconnect(self.__onDisconnect)
    socket.onMessage(self._handle_message)

    self._socket = socket

  def _handle_message(self, message: str) -> None:
    messageObject = json.loads(message)
    if 'topic' in messageObject:
      cb = self._callbacks.get(messageObject['topic'])
      if cb:
        if 'payload' in messageObject:
          cb(messageObject['payload'])
        else:
          print(f"Error handling message: {messageObject}")

  async def __onConnect(self):
    # Send API handshake before any user-registered onConnect
    self._socket.send(json.dumps(ApiVersion))
    # Call user defined onConnect if it exists
    if self._userOnConnect is not None:
      await self._userOnConnect()

  def __onDisconnect(self) -> None:
    # Signal all live topic iterators to stop
    for cancelEvent in self._topicCancelEvents.values():
      cancelEvent.set()
    self._topicCancelEvents.clear()
    self._callbacks.clear()
    # Call user defined onDisconnect if it exists
    if self._userOnDisconnect is not None:
      self._userOnDisconnect()

  def onConnect(self, callback: Callable[[], Coroutine[Any, Any, None]]) -> None:
    """
    Set the async function to call when a connection is established.

    :param `callback` - Async function to execute.
    """
    self._userOnConnect = callback

  def onDisconnect(self, callback: Callable[[], None]):
    """Set the function to execute when socket is disconnected."""
    self._userOnDisconnect = callback

  async def connect(self):
    """Connect to OpenSpace."""
    await self._socket.connect()

  def disconnect(self):
    """Disconnect from OpenSpace."""
    self._socket.disconnect()

  def startTopic(self, type: str, payload: Any, cancelPayload: Any = None) -> Topic:
    """
    Initialize a new channel of communication.

    :param `type` - A string specifying the type of topic to construct. See OpenSpace's
    server.cpp for available topic types.\n
    :param `payload` - An object representing the topic.\n
    :param `cancelPayload` - Optional payload to send before closing the topic.\n
    :return - A Topic object.
    """
    if not isinstance(type, str):
      raise ValueError("Topic type must be a string")

    topicId = self._nextTopicId
    self._nextTopicId += 1

    messageObject = {
      'topic': topicId,
      'type': type,
      'payload': payload
    }

    self._socket.send(json.dumps(messageObject))

    queue: asyncio.Queue[Any] = asyncio.Queue()
    self._callbacks[topicId] = lambda payload: queue.put_nowait(payload)

    cancelEvent = asyncio.Event()
    self._topicCancelEvents[topicId] = cancelEvent

    async def iterator() -> AsyncGenerator[Any, None]:
      while not cancelEvent.is_set():
        try:
          # Race the queue against both the cancel event so we don't block indefinitely
          # when the connection drops
          get = asyncio.ensure_future(queue.get())
          cancel_wait = asyncio.ensure_future(cancelEvent.wait())
          done, pending = await asyncio.wait(
            [get, cancel_wait],
            return_when=asyncio.FIRST_COMPLETED
          )
          # Clean up pending tasks to avoid leaks
          for task in pending:
            task.cancel()
          if cancelEvent.is_set():
            # Topic was cancelled, exit the iterator
            break
          # If the get completed successfully, we have a new value to yield
          if get in done and not get.cancelled():
            yield get.result()
        except Exception as e:
          print(f"Error in topic {topicId} iterator: {e}")
          print_exc()
          break
      # Topic has been canceled, remove callback and cancel event
      self._callbacks.pop(topicId, None)
      self._topicCancelEvents.pop(topicId, None)


    def talk(payload: Any) -> None:
      messageObject = {
        'topic': topicId,
        'payload': payload
      }
      self._socket.send(json.dumps(messageObject))

    def cancel () -> None:
      if cancelPayload is not None:
        talk(cancelPayload)
      cancelEvent.set()
      self._callbacks.pop(topicId, None)
      self._topicCancelEvents.pop(topicId, None)

    return Topic(iterator(), talk, cancel)

  async def authenticate(self, secret) -> Any:
    """
    Authenticate this client. This must be done if the client is not whitelisted in the
    openspace.cfg.

    :param `secret` - The secret used to authenticate with OpenSpace.
    """
    topic = self.startTopic('authorize', { "password": secret })
    try:
      return await topic.next()
    finally:
      topic.cancel()

  def setProperty(self, property: str, value: Any) -> None:
    """
    Set a property

    :param `property` - The URI of the property to set.\n
    :param `value` - The value to set the property to.
    """
    if not isinstance(property, str):
      raise ValueError("Property must be a string")

    topic = self.startTopic('set', { "property": property, "value": value })
    topic.cancel()

  async def getProperty(self, property: str) -> Any:
    """
    Get a property.

    :param `property` the URI of the property to get.\n
    :return `value` - The value of the property.
    """
    if not isinstance(property, str):
      raise ValueError("Property must be a string")

    topic = self.startTopic('get', { "property": property })
    try:
      return await topic.next()
    finally:
      topic.cancel()

  async def getDocumentation(self, type: str) -> Any:
    """
    Get documentation from OpenSpace.

    :param type - The type of documentation to get. For available types, check
    documentationtopic.cpp in OpenSpace core.\n
    :return An object representing the requested documentation
    """
    topic = self.startTopic('documentation',  { "type": type } )
    try:
      return await topic.next()
    finally:
      topic.cancel()

  def subscribeToProperty(self, property: str) -> Topic:
    """
    Subscribe to a property.

    :param `property`- The URI of the property to subscribe to.\n
    :return `Topic` - A topic object to represent the subscription topic. When cancelled,
    this object will unsubscribe to the property.
    """
    if not isinstance(property, str):
      raise ValueError("Property must be a string")

    return self.startTopic(
      'subscribe',
      { 'event': 'start_subscription', 'uri': property },
      { "event": "stop_subscription" }
    )

  def subscribeToEvent(self, events: str | list[str]) -> Topic:
    """
    Subscribe to an event.

    :param `event` - The name of the event to subscribe to. For available events, check
    event.h in OpenSpace core module.\n
    :return `Topic` - A topic object to represent the subscription topic.
    when cancelled, this object will unsubscribe to the event.
    """
    if not isinstance(events, str) and not isinstance(events, list):
      raise ValueError("Event must be a string or list of strings")

    if isinstance(events, list):
      for event in events:
        if not isinstance(event, str):
          raise ValueError(f"Event {event} in list is not a string")

    return self.startTopic(
      'event',
      { 'eventType': events, 'event': 'start_subscription' },
      { 'eventType': events, 'event': 'stop_subscription' }
    )

  def subscribeToLogMessages(
    self,
    settings: dict,
    callback: Callable[[Any], None]
  ) -> Callable[[], Coroutine[Any, Any, None]]:
    """ Subscribe to error messages. \n
    :param `settings` - The settings for the error subscription. Possible settings are\n
    | `timeStamping`: [True, False] - Whether the error messages should be timestamped.
    | `dateStamping`: [True, False] - Whether the error messages should be datestamped.
    | `categoryStamping`: [True, False] - Whether the error messages should be category stamped.
    | `logLevelStamping`: [True, False] - Whether the error messages should be log level stamped.
    | `logLevel`: [All, Trace, Debug, Info, Warning, Error, Fatal, None] - The log level to subscribe to.\n
    :param `callback` - The callback function to call when new messages are recieved from
    OpenSpace. The function takes one parameter `message`\n
    :return `cancel` - A coroutine function, when called the topic unsubscribes from the
    log messages.
    """
    if not isinstance(settings, dict):
      raise ValueError("Settings must be a dictionary")

    topic = self.startTopic(
      'errorLog',
      { 'event': 'start_subscription', 'settings': settings },
      { "event": "stop_subscription"}
    )

    async def loop() -> None:
      async for message in topic:
        callback(message)

    task = asyncio.create_task(loop())

    async def cancel() -> None:
      topic.cancel()
      task.cancel()

      try:
        await task # Cancel the loop
      except asyncio.CancelledError:
        # Task was cancelled, proceed to cleanup
        pass

    return cancel

  async def executeLuaScript(
    self,
    script: str,
    getReturnValue: bool = True,
    shouldBeSynchronized: bool = True
  ) -> Any:
    """
    Execute a Lua script.

    :param `script` - The Lua script to execute.\n
    :param `getReturnValue` - Specified whether the return value should be collected.\n
    :param `shouldBeSynchronized - Specified whether the script should be synchronized on
    a cluster.\n
    :return The return value of the script, if `getReturnValue` is true, otherwise None.
    """
    if not isinstance(script, str):
      raise ValueError("Script must be a string")

    topic = self.startTopic('luascript', {
      'script': script,
      'return': getReturnValue,
      'shouldBeSynchronized': shouldBeSynchronized
    })

    if not getReturnValue:
      topic.cancel()
      return None

    try:
      return await topic.next()
    finally:
      topic.cancel()

  async def executeLuaFunction(
    self,
    function: str,
    args: list[Any],
    getReturnValue: bool = True
  ) -> Any:
    """
    Executa a lua function from the OpenSpace library.

    :param `function`- The Lua function to execute, for example
    `openspace.addSceneGraphNode`.\n
    :param `args`- The function arguments.\n
    :param `getReturnValue`- Specified whether the return value should be collected.\n
    :return The return value of the script, if `getReturnValue` is true, otherwise None.
    """
    if not isinstance(function, str):
      raise ValueError("Function type must be a string")

    topic = self.startTopic('luascript', {
      'function': function,
      'arguments': args,
      'return': getReturnValue
    })

    if not getReturnValue:
      topic.cancel()
      return None
    try:
      return await topic.next()
    finally:
      topic.cancel()

  async def library(self, wrapper: Callable | None = None) -> NamedTuple:
    """
    Get an object representing the OpenSpace lua libarary.

    Returns a NamedTuple tree mirroring the OpenSpace Lua namesace, where each leaf is an
    async function that executes the corresponding Lua function via the API.

    :param wrapper - If provided, wraps each async API calls. Can be used to make calls
    synchronous in interactive environments.\n
    :return - The lua library, mapped to async python functions.
    """
    async def async_lua_call(functionName: str, *args: Any) -> Any:
      try:
        result = await self.executeLuaFunction(functionName, list(args))
        if result:
          return result['1']
        return None
      except Exception as e:
        print(f"Lua exception: {e}")

    documentation = await self.getDocumentation('lua')

    pyLibrary: dict[str, Any] = {}

    for library in documentation:
      libraryName: str = library["name"]

      if not libraryName or libraryName == '':
        # Direct openspace.* functions, add to top level
        functions  = library["functions"]
        for func in functions:
          functionName = func["name"]
          fullFunctionName = f"openspace.{functionName}"
          luaCall = partial(async_lua_call, fullFunctionName)
          if wrapper is not None:
            luaCall = partial(wrapper, luaCall)
          pyLibrary[functionName] = luaCall
      else:
        # Namespaced functions, add to sublibrary
        subPyLibrary: dict[str, Any] = {}
        functions = library["functions"]
        for func in functions:
          functionName = func["name"]
          fullFunctionName = f"openspace.{libraryName}.{functionName}"
          luaCall = partial(async_lua_call, fullFunctionName)
          if wrapper is not None:
            luaCall = partial(wrapper, luaCall)
          subPyLibrary[functionName] = luaCall
        pyLibrary[libraryName] = subPyLibrary
    return toNamedTuple(pyLibrary, "openspace")
