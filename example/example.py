import asyncio
import openspace
from openspace import toNamedTuple

ADDRESS = 'localhost'
PORT = 4681

# Create an OpenSpaceApi instance with the OpenSpace address and port
api = openspace.Api(ADDRESS, PORT)

# This event is used to cleanly exit the event loop.
disconnect = asyncio.Event()

#--------------------------------TEST FUNCTIONS--------------------------------
# Define a callback function to handle the received payload
def event_callback(result):
  print("event_callback result:", result)

async def scaleEarth(value: float):
  print("Scaling Earth")

  property = "Scene.Earth.Scale.Scale"
  data = await api.getProperty(property)
  data = toNamedTuple(data)
  print(f"Current scale value: {data.value.value}")
  api.setProperty(property, value)

async def subscribeToEarthScaleUpdates():
  print("Subscribing to Earth scale updates")

  topic = api.subscribeToProperty("Scene.Earth.Scale.Scale")
  i = 0
  async for data in topic:
    print(f"Waiting for Earth scale update {i}/3")
    print(f"Earth scale update data: {data}")
    if i >= 3:
      topic.cancel()
    i += 1

async def subscribeToEventOnce(events):
  topic = api.subscribeToEvent(events)

  print(f"SubscribeToEventOnce: Waiting for {events} to fire...")
  async for result in topic:
    print("SubscribeToEventOnce: Event fired: ", result)
    topic.cancel()

async def subscribeToEventWithCallback(events, callback):
  topic = api.subscribeToEvent(events)
  i = 0
  print(f"SubscribeToEventWithCallback: Subscription callback waiting for {events} to fire...")
  async for result in topic:
    print(f"SubscibeToEventWithCallback: Event fired: {result}")
    callback(result)
    i+=1
    if i >= 2:
      topic.cancel()
      print("Cancelled SubscribeToEventWithCallback")

async def getTime(openspace):
  time = await openspace.time.UTC()
  print(f"Current simulation time: {time}")


async def getGeoPositionForCamera(openspace):
  pos = await openspace.globebrowsing.geoPositionForCamera()
  print(f"Geo position from camera: {pos}")

async def addSceneGraphNode(openspace):
  identifier = "TestNode"
  name = "Test Node"

  node = {
    "Identifier": identifier,
    "Name": name,
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

  await openspace.setPropertyValue("NavigationHandler.OrbitalNavigator.Anchor", identifier)
  await openspace.setPropertyValue("NavigationHandler.OrbitalNavigator.RetargetAnchor", None)

#--------------------------------MAIN FUNCTION--------------------------------
async def main(openspace):
  await scaleEarth(0.9)
  await getTime(openspace)
  await getGeoPositionForCamera(openspace)
  await addSceneGraphNode(openspace)

  # Create a task to not block event loop
  earthScaleTask = asyncio.create_task(subscribeToEarthScaleUpdates())
  asyncio.create_task(subscribeToEventOnce(["RenderableEnabled"]))

  await earthScaleTask

  event_Task = asyncio.create_task(
    subscribeToEventWithCallback(
      ["RenderableEnabled", "RenderableDisabled"],
      event_callback
    )
  )

  await event_Task

  disconnect.set()

async def onConnect():
  PASSWORD = ''
  result = await api.authenticate(PASSWORD)
  if not result["status"] == 'authorized':
    disconnect.set()
    return

  print("Connected to OpenSpace")
  openspace = await api.library()

  # Create a main task to run all function logic
  asyncio.create_task(main(openspace), name="Main")

def onDisconnect():
  print("Disconnected from OpenSpace")
  # If connection failed this helps the program exit gracefully
  disconnect.set()

api.onConnect(onConnect)
api.onDisconnect(onDisconnect)

# Main loop serves as an entry point to allow for authentication before running any other
# logic. This part can be skipped if no authentication is needed, reducing the overhead of
# creating multiple tasks before main() is run.
async def mainLoop():
  await api.connect()
  # Wait for the disconnect event to be set
  await disconnect.wait()
  api.disconnect()

asyncio.run(mainLoop())