import asyncio
import openspace

ADDRESS = 'localhost'
PORT = 4681
# Create an OpenSpaceApi instance with the OpenSpace address and port
os = openspace.Api(ADDRESS, PORT)

# This event is used to cleanly exit the event loop.
disconnect = asyncio.Event()

#--------------------------------TEST FUNCTIONS--------------------------------
# Define a callback function to handle the received payload
def event_callback(result):
    print("event_callback:", result)

async def scaleEarth(value):
    print("Scaling Earth")

    property = "Scene.Earth.Scale.Scale"
    data = await os.getProperty(property)
    data = os.toNamedTuple(data)

    print(f"Current scale value: {data.Value}")
    os.setProperty(property, value)

async def subscribeToEarthScaleUpdates():
    print("Subscribing to Earth scale updates")

    subscription = os.subscribeToProperty("Scene.Earth.Scale.Scale")
    # We can iterate the subscription using by looping nextValue()
    i = 0
    while i < 3:
        print("Waiting for Earth scale update...")
        result = await os.nextValue(subscription)
        dic = os.toNamedTuple(result)
        print(f"{dic.Description.Identifier} changed to {dic.Value}")
        i += 1
    subscription.cancel()

    ## Or using async for loop
    # async for future in subscription.iterator():
    #     result = await future
    #     dic = api.toNamedTuple(result)
    #     print(f"{dic.Description.Identifier} changed to {dic.Value}")
    #     if i > 3:
    #         subscription.cancel()
    #     i += 1

async def subscribeToEventOnce(events):
    topic = os.subscribeToEvent(events)

    async for future in topic.iterator():
        print(f"SubscribeToEventOnce: Waiting for {events} to fire...")
        result = await future
        print("Event fired: ", result)
        topic.cancel()

async def subscribeToEventWithCallback(events, callback):
    topic = os.subscribeToEvent(events)
    j = 0
    async for future in topic.iterator():
        print(f"SubscribeToEventWithCallback: Subscription callback waiting for {events} to fire...")
        data = await future
        callback(data)
        if j >= 1:
            topic.cancel()
            print("Cancelled SubscribeToEventWithCallback")
        j += 1

async def getTime(openspace):
    time = await openspace.time.UTC()
    # equivalent to:
    # time = await openspace['time']['UTC']()
    print(f"Current simulation time: {time}")

async def getGeoPosition(openspace):
    pos = await openspace.globebrowsing.localPositionFromGeo("Earth", 10, 10, 10)
    print(f"Earth geo position: {pos}")

async def getGeoPositionForCamera(openspace):
    pos = await openspace.globebrowsing.geoPositionForCamera()
    print(f"Geo position from camera: {pos}")

async def addSceneGraphNode(openspace):
    IDENTIFIER = "TestNode"
    NAME = "Test Node"

    node = {
        "Identifier": IDENTIFIER,
        "Name": NAME,
        "Parent": "Earth",
        "Transform": {
            "Type": "GlobeTranslation",
            "Globe": "Earth",
            "Latitude": 0,
            "Longitude": 0,
            "FixedAltitude": 10
        },
        "GUI": {
            "Path": "/MyTest/Test",
            "Name": "TestNode"
        }
    }

    await openspace.addSceneGraphNode(node)
    print("Added scene graph node")

    await openspace.setPropertyValue("NavigationHandler.OrbitalNavigator.Anchor", IDENTIFIER)
    await openspace.setPropertyValue("NavigationHandler.OrbitalNavigator.RetargetAnchor", None)

#--------------------------------MAIN FUNCTION--------------------------------
async def main(openspace):

    await scaleEarth(0.9)
    await getTime(openspace)
    await getGeoPosition(openspace)
    await getGeoPositionForCamera(openspace)
    await addSceneGraphNode(openspace)

    # Create a task to not block event loop
    earthScale_Task = asyncio.create_task(subscribeToEarthScaleUpdates())

    asyncio.create_task(subscribeToEventOnce(["RenderableEnabled"]))

    await earthScale_Task

    event_Task = asyncio.create_task(subscribeToEventWithCallback(
        ["RenderableEnabled", "RenderableDisabled"], event_callback))

    await event_Task

    disconnect.set()

async def onConnect():
    PASSWORD = ''
    res = await os.authenticate(PASSWORD)
    if not res[1] == 'authorized':
        disconnect.set()
        return

    print("Connected to OpenSpace")
    openspace = await os.singleReturnLibrary()

    # Create a main task to run all function logic
    asyncio.create_task(main(openspace), name="Main")

def onDisconnect():
    if asyncio.get_event_loop().is_running():
        asyncio.get_event_loop().stop()
    print("Disconnected from OpenSpace")
    # If connection failed this helps the program exit gracefully
    disconnect.set()

os.onConnect(onConnect)
os.onDisconnect(onDisconnect)

# Main loop serves as an entry point to allow for authentication before running any other
# logic. This part can be skipped if no authentication is needed, reducing the overhead of
# creating multiple tasks before main() is run.
async def mainLoop():
    os.connect()
    # Wait for the disconnect event to be set
    await disconnect.wait()
    os.disconnect()

loop = asyncio.new_event_loop()
loop.run_until_complete(mainLoop())
loop.run_forever()
