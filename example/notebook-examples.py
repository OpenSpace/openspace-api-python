import asyncio
from src.api import OpenSpaceApi, DotDict

ADDRESS = 'localhost'
PORT = 4681

api = OpenSpaceApi(ADDRESS, PORT)

async def setPause():
    api.connect()
    openspace = await api.singleReturnLibrary()
    await openspace.time.setPause(True)

async def goToGeo():
    api.connect()

    lat = 40.7208636
    lon = -74.0094477
    altitude = 220

    openspace = await api.singleReturnLibrary()
    await openspace.globebrowsing.goToGeo(lat, lon, altitude)

async def setYourTime():
    import time
    import datetime
    timestring = "2021-03-09T23:42:02.393"
    timestamp = time.mktime(datetime.datetime.strptime(timestring, "%Y-%m-%dT%H:%M:%S.%f").timetuple())
    j200offset = datetime.datetime(2000,1,1,12) - datetime.datetime(1970,1,1)
    timestamp -= j200offset.total_seconds()

    interval = 300 # in seconds
    number_of_photos = 20

    api.connect()
    openspace = await api.singleReturnLibrary()

    for i in range(0, number_of_photos):
        await openspace.time.setTime(timestamp)
        time.sleep(0.1) # adjust if low fps
        await openspace.takeScreenshot()
        time.sleep(0.25) # adjust if hires screenshot
        timestamp += interval

async def addLayersToGlobe():
    # ... Prepare the layers 
    api.connect()
    openspace = await api.singleReturnLibrary()
    output_path = "C:/os/OpenSpaceData/Moon2/"
    globe_for_layers = "Moon"
    # await openspace.globebrowsing.addBlendingLayersFromDirectory(output_path, globe_for_layers)
    # refresh menu
    await openspace.setPropertyValueSingle("Modules.CefWebGui.Reload", None)


# Uncomment function to run
# asyncio.run(setPause())
# asyncio.run(goToGeo())
# asyncio.run(setYourTime())
# asyncio.run(addLayersToGlobe())
