import asyncio
import json
from traceback import print_exc
from .topic import Topic
from .socketwrapper import SocketWrapper
from typing import Callable, NamedTuple
from collections import namedtuple


def toNamedTuple(content: dict, name: str = "namedtuple") -> NamedTuple:
    """ Recursively converts a `dictionary` to a `namedtuple`. """

    T = namedtuple(name, content.keys())
    values = []
    for k, v in content.items():
        if isinstance(v, dict):
            values.append(toNamedTuple(v, k))
        else:
            values.append(v)

    return T(*values)


class Api:
    """ Construct an instance of the OpenSpace API. \n
    :param socket - An instance of SocketWrapper.
    The socket should not be connected prior to calling this constructor. """

    def __init__(self, ADDRESS, PORT):
        self._callbacks = {}
        self._nextTopicId = 0

        socket = SocketWrapper(ADDRESS, PORT)
        async def __onConnect():
            pass
        socket.onConnect(__onConnect)
        socket.onDisconnect(lambda: None)
        socket.onMessage(self._handle_message)

        self._socket = socket

    def _handle_message(self, message):
        messageObject = json.loads(message)
        if 'topic' in messageObject:
            cb = self._callbacks.get(messageObject['topic'])
            if cb:
                if 'payload' in messageObject:
                    cb(messageObject['payload'])
                else:
                    print(f"Error handling message: {messageObject}")
    def onConnect(self, callback: Callable[[], None]):
        """ Set the function to execute when connection is established. \n
        :param `callback` - Async function to execute. """

        self._socket.onConnect(callback)


    def onDisconnect(self, callback: Callable[[], None]):
        """ Set the function to execute when socket is dicsonnected. """

        self._socket.onDisconnect(callback)

    async def connect(self):
        """ Connect to OpenSpace. """

        await self._socket.connect()

    def disconnect(self):
        """ Disconnect from OpenSpace. """

        self._socket.disconnect()

    def startTopic(self, type: str, payload) -> Topic:
        """ Initialize a new channel of communication. \n

        :param `type` - A string specifying the type of topic to construct. \n
        See OpenSpace's server module for available topic types.
        :param `payload` - An object representing the topic \n
        :return - A Topic object. """

        if not isinstance(type, str):
            raise ValueError("Topic type must be a string")

        topic = self._nextTopicId
        self._nextTopicId += 1

        messageObject = {
            'topic': topic,
            'type': type,
            'payload': payload
        }

        self._socket.send(json.dumps(messageObject))

        cancel_event = asyncio.Event()

        def cancel ():
            # Temp fix to remove callback, see TODO in iterator()
            cancel_event.set()
            self._callbacks.pop(topic, None)

        async def iterator():
            # TODO: if we are just iterating once we never return to the while
            # loop to check if cancel_event is set. As such we wont remove the callback
            # function.
            queue = asyncio.Queue()
            self._callbacks[topic] = lambda payload: queue.put_nowait(payload)
            while not cancel_event.is_set():
                try:
                    # Yield the coroutine for the caller to await, this should allow us
                    # to await several callbacks without them blocking eachother.
                    yield queue.get()
                except Exception as e:
                    print("ERROR: in topic:", topic, e)
                    print_exc()
                    break

            # Topic has been canceled, remove callback
            self._callbacks.pop(topic, None)

        it = iterator()

        def talk(payload):
            messageObject = {
                'topic': topic,
                'payload': payload
            }
            self._socket.send(json.dumps(messageObject))


        return Topic(it, talk, cancel)

    async def nextValue(self, topic: Topic):
        """ Utility function to iterate a topic and retrieve the next value. """

        future = await anext(topic.iterator())
        result = await future
        return result

    async def authenticate(self, secret):
        """ Authenticate this client. \n
        This must be done if the client is not whitelisted in the openspace.cfg. \n
        :param `secret` - The secret used to authenticate with OpenSpace. """

        topic = self.startTopic('authorize', { "key": secret })
        response = await self.nextValue(topic)
        topic.cancel()
        return response

    def setProperty(self, property, value):
        """ Set a property \n
        :param `property` - The URI of the property to set. \n
        :param `value` - The value to set the property to. """

        if not isinstance(property, str):
            raise ValueError("Property must be a string")

        topic = self.startTopic('set', { "property": property, "value": value })
        topic.cancel()

    async def getProperty(self, property):
        """ Get a property. \n
        :param `property` the URI of the property to get.\n
        :return `value` - The value of the property. """

        if not isinstance(property, str):
            raise ValueError("Property must be a string")

        topic = self.startTopic('get', { "property": property })

        response = await self.nextValue(topic)
        topic.cancel()

        return response

    async def getDocumentation(self, type: str):
        """ :param type - The type of documentation to get. For available types, check
        documentationtopic.cpp in OpenSpace's server module. """

        topic = self.startTopic('documentation',  { "type": type } )

        response = await self.nextValue(topic)
        topic.cancel()

        return response

    def subscribeToProperty(self, property):
        """ Subscribe to a property.\n
        :param `property`- The URI of the property to subscribe to.\n
        :return `Topic` - A topic object to represent the subscription topic.
        when cancelled, this object will unsubscribe to the property. """
        if not isinstance(property, str):
            raise ValueError("Property must be a string")

        topic = self.startTopic('subscribe', {
            'event': 'start_subscription',
            'property': property
        })

        def cancel():
            topic.talk({
                'event': 'stop_subscription'
            })
            topic.cancel()

        return Topic(topic.iterator(), topic.talk, cancel)

    def subscribeToEvent(self, events):
        """ Subscribe to an event. \n
        :param `event` - The name of the event to subscribe to. For available events,
        check event.h in OpenSpace core module. \n
        :return `Topic` - A topic object to represent the subscription topic.
        when cancelled, this object will unsubscribe to the event. """

        if not isinstance(events, str) and not isinstance(events, list):
            raise ValueError("Event must be a string or list of strings")

        if isinstance(events, list):
            for event in events:
                if not isinstance(event, str):
                    raise ValueError(f"Event {event} in list is not a string")

        topic = self.startTopic('event', {
            'event': events,
            'status': 'start_subscription'
        })

        def cancel():
            topic.talk({
                "event": events,
                'status': 'stop_subscription'
            })
            topic.cancel()

        return Topic(topic.iterator(), topic.talk, cancel)


    def subscribeToLogMessages(self, settings, callback: Callable[[any], None]):
        """ Subscribe to error messages. \n
        :param `settings` - The settings for the error subscription. Possible settings are \n
        | `timeStamping`: [True, False] - Whether the error messages should be timestamped.
        | `dateStamping`: [True, False] - Whether the error messages should be datestamped.
        | `categoryStamping`: [True, False] - Whether the error messages should be category stamped.
        | `logLevelStamping`: [True, False] - Whether the error messages should be log level stamped.
        | `logLevel`: [All, Trace, Debug, Info, Warning, Error, Fatal, None] - The log level to subscribe to.

        :param `callback` - The callback function to call when new messages are recieved
        from OpenSpace. The function takes one parameter `message`

        :return `cancel` - A coroutine function, when called the topic unsubscribes
        from the log messages.
        """
        if not isinstance(settings, dict):
            raise ValueError("Settings must be a dictionary")

        topic = self.startTopic('errorLog', {
            'event': 'start_subscription',
            'settings': settings
        })

        cancelTopic = asyncio.Event()

        async def cancel():
            cancelTopic.set()
            task.cancel() # Cancel the loop task

            try:
                await asyncio.gather(task) # Await the cancellation
            except asyncio.CancelledError:
                # Task was cancelled, proceed to cleanup
                pass

            topic.talk({
                'event': 'stop_subscription'
            })
            topic.cancel()

        async def subscribeLoop():
            async for future in topic.iterator():
                message = await future

                if cancelTopic.is_set():
                    return

                callback(message)

        task = asyncio.create_task(subscribeLoop())
        return cancel

    async def executeLuaScript(self, script, getReturnValue = True, shouldBeSynchronized = True):
        """ Execute a lua script. \n
        :param `script` - The lua script to execute. \n
        :param `getReturnValue`- Specified whether the return value should be collected. \n
        :param `shouldBeSynchronized  - Specified whether the script should be
        synchronized on a cluster. \n
        :return The return value of the script, if `getReturnValue` is true, otherwise
        undefined. """

        if not isinstance(script, str):
            raise ValueError("Script must be a string")

        topic = self.startTopic('luascript', {
            'script': script,
            'return': getReturnValue,
            'shouldBeSynchronized': shouldBeSynchronized
        })

        if getReturnValue:
            response = await self.nextValue(topic)
            topic.cancel()
            return response
        else:
            topic.cancel()

    async def executeLuaFunction(self, function: str, args, getReturnValue = True):
        """ Executa a lua function from the OpenSpace library. \n
        :param `function`- The lua function to execute (for example
        `openspace.addSceneGraphNode`) \n
        :param `getReturnValue`- Specified whether the return value should be collected. \n
        :return The return value of the script, if `getReturnValue` is true, otherwise
        undefined. """

        if not isinstance(function, str):
            raise ValueError("Function type must be a string")

        payload = {
            'function': function,
            'arguments': args,
            'return': True
        }
        topic = self.startTopic('luascript', payload)

        if getReturnValue:
            response = await self.nextValue(topic)
            topic.cancel()
            return response
        else:
            topic.cancel()

    async def library(self) -> dict:
        """ Get an object representing the OpenSpace lua libarary. \n
        :return - The lua library, mapped to async python functions. """

        def generateAsyncSingleRetFunction(functionName):
            async def fun(*args):
                try:
                    luaTable = await self.executeLuaFunction(functionName, args)
                    if luaTable:
                        return luaTable['1']
                    return None
                except Exception as e:
                    print("Lua exception error: \n", e)
            return fun

        docs = await self.getDocumentation('lua')

        pyLibrary = {}

        for lib in docs:
            subPyLibrary = {}
            libraryName = lib['library']
            if not libraryName: # library is empty string
                subPyLibrary = pyLibrary
            else:
                pyLibrary[libraryName] = {}
                subPyLibrary = pyLibrary[libraryName] # reference to the sublibrary

            for func in lib['functions']:
                _lib = '' if subPyLibrary == pyLibrary else libraryName + '.'
                fullFunctionName = 'openspace.' + _lib + func['name']

                subPyLibrary[func['name']] = generateAsyncSingleRetFunction(fullFunctionName)

        return toNamedTuple(pyLibrary, libraryName)

    async def singleReturnLibrary(self):
        """ Get an object representing the OpenSpace lua library. \n
        :return - The lua library, mapped to async python functions. This method only
        returns the first return value. """

        return await self.library(False)
