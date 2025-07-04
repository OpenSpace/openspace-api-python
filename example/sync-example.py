import asyncio
import openspace

# This is an example of how to make synchronous calls to the API
# This is not so useful in scripts but has its use in interactive shells, instead of prepending
# every call with `await`.

ADDRESS = 'localhost'
PORT = 4681
# Create an OpenSpaceApi instance with the OpenSpace address and port
api = openspace.Api(ADDRESS, PORT)

# You might want to handle this differently according to your environment or use-case.
# For instance, this works in a regular python shell or in IPython but `python3 -m asyncio` is
# different.
loop = asyncio.new_event_loop()
def sync_wrapper(f, *args, **kwargs):
    return loop.run_until_complete(f(*args, **kwargs))

# warning: all async calls must be performed on the same loop

loop.run_until_complete(api.connect())
sync_os = loop.run_until_complete(api.library(sync_wrapper))

# Calls to methods of `sync_os` will block until the call is made and a result is returned:
sync_os.printInfo("foo")
print(sync_os.propertyValue("Scene.Earth.Scale.Scale"))

api.disconnect()
