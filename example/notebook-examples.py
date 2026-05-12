import asyncio
import openspace as OpenSpace

ADDRESS = 'localhost'
PORT = 4681

# Each function below is self-contained and can be run independetly from a notebook
# cell with `await functionName()`, or from a script with `asyncio.run(functionName())`
#
# Note: In Jupyter notebooks, the event loop is already running, so use
# `await functionName()` directly in a cell rather than `asyncio.run(...)`.

async def setPause():
  api = OpenSpace.Api(ADDRESS, PORT)
  await api.connect()
  openspace = await api.library()
  await openspace.time.setPause(True)
  api.disconnect()

async def goToGeo():
  api = OpenSpace.Api(ADDRESS, PORT)
  await api.connect()

  lat = 40.7208636
  lon = -74.0094477
  altitude = 220

  openspace = await api.library()
  # print(openspace.navigation)
  await openspace.navigation.jumpToGeo("", lat, lon, altitude)
  api.disconnect()

async def setYourTime():
  import time
  import datetime
  timestring = "2021-03-09T23:42:02.393"
  timestamp = time.mktime(datetime.datetime.strptime(timestring, "%Y-%m-%dT%H:%M:%S.%f").timetuple())
  j200offset = datetime.datetime(2000,1,1,12) - datetime.datetime(1970,1,1)
  timestamp -= j200offset.total_seconds()

  interval = 300 # in seconds
  number_of_photos = 20

  api = OpenSpace.Api(ADDRESS, PORT)
  await api.connect()
  openspace = await api.library()

  for i in range(0, number_of_photos):
    await openspace.time.setTime(timestamp)
    await asyncio.sleep(0.1) # adjust if low fps
    await openspace.takeScreenshot()
    await asyncio.sleep(0.25) # adjust if hires screenshot
    timestamp += interval

  api.disconnect()

async def addLayersToGlobe():
  # ... Prepare the layers
  api = OpenSpace.Api(ADDRESS, PORT)
  await api.connect()
  openspace = await api.library()
  output_path = "C:/os/OpenSpaceData/Moon2/"
  globe_for_layers = "Moon"
  # await openspace.globebrowsing.addBlendingLayersFromDirectory(output_path, globe_for_layers)
  api.disconnect()

# Uncomment function to run as a script:
asyncio.run(setPause())
# asyncio.run(goToGeo())
# asyncio.run(setYourTime())
# asyncio.run(addLayersToGlobe())

# In a Jupyter notebook, run a cell with:
# `await setPause()`