# openspace-api-python
Python library to interface with [OpenSpace](https://github.com/OpenSpace/OpenSpace) using TCP sockets.

**Work in progress** - Both the API and library are still under active development and are subject to change.

## Install
Stable releases are published on [PyPI](https://pypi.org/project/openspace-api/). Install the latest version with:

```sh
pip install openspace-api
```

## Quick start

```python
import asyncio
import openspace as OpenSpace

api = OpenSpace.Api('localhost', 4681)
disconnect = asyncio.Event()

async def onConnect():
  openspace = await api.library()
  time = await openspace.time.UTC()
  print(f"Current simulation time: {time}")
  disconnect.set()

def onDisconnect():
  disconnect.set()

api.onConnect(onConnect)
api.onDisconnect(onDisconnect)

async def main():
  await api.connect()
  await disconnect.wait()

asyncio.run(main())
```

## Examples

Install the example dependencies first:

```sh
pip install -r example/requirements.txt
```

  - [example.py](https://github.com/OpenSpace/openspace-api-python/blob/master/example/example.py) - Async script demonstrating get/set property, property subscriptions, event subscriptions, calling Lua library functions, and adding scene graph nodes. Run with:
  ```sh
  python example/example.py
  ```
  - [example/sync-example.py](https://github.com/OpenSpace/openspace-api-python/blob/master/example/sync-example.py) - Shows how to wrap async API calls to make them synchronous, useful in interactive shells (Python REPL, IPython). Run with:
  ```sh
  python example/sync-example.py
  ```
  - [example/notebook-examples.py](https://github.com/OpenSpace/openspace-api-python/blob/master/example/notebook-examples.py) - Self-contained async functions designed for Jupyter notebooks (`await functionName()`) or scripts (`asyncio.run(functionName())`). Covers pausing simulation, navigating to geo coordinates, setting time, and adding globe layers.

## Requirements
  - Python 3.10+
  - A running instance of [OpenSpace](https://github.com/OpenSpace/OpenSpace)
