from typing import Any, AsyncGenerator, Callable

class Topic:
  """
  A channel to communicate with OpenSpace.

  Topics are returned by `Api.start_topic` and should not be constructed directly.
  """

  def __init__(
    self,
    iterator: AsyncGenerator[Any, None],
    talk: Callable[[Any], None],
    cancel: Callable[[], None]
  ):
    """
    :param `iterator` - An async iterator to represent data from OpenSpace.\n
    :param `talk` - The function used to send messages.\n
    :param `cancel` - The function used to cancel the topic.
    """
    self._iterator = iterator
    self._talk = talk
    self._cancel = cancel

  def talk(self, data: Any) -> None:
    """
    Send data within this topic.

    :param `data` - A Python object to send. Must be possible to encode into JSON.
    """
    return self._talk(data)

  def __aiter__(self) -> AsyncGenerator[Any, None]:
    """ Allow `async for value in topic` iteration."""
    return self._iterator

  async def __anext__(self) -> Any:
    """
    Get the next value from OpenSpace.

    :raises `StopAsyncIteration`: If the topic has been cancelled
    """
    return await self._iterator.__anext__()

  async def next(self) -> Any:
    """
    Get the next value from OpenSpace. Alias for `await topic.__anext__()`.

    :raises `StopAsyncIteration`: If the topic has been cancelled.
    """
    return await self.__anext__()

  def cancel(self):
    """Cancel the topic. After calling this, the topic should not be used again."""
    return self._cancel()
