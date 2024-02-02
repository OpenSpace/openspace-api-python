class Topic:
    """ A channel to communicate with OpenSpace. """
    
    def __init__(self, iterator, talk, cancel):
        """ Construct a topic. (Only for internal use)
        :param `iterator` - An async iterator to represent data from OpenSpace.
        :param `talk` - The function used to send messages.
        :param `cancel` - The function used to cancel the topic. """

        self._iterator = iterator
        self._talk = talk
        self._cancel = cancel

    def talk(self, data):
        """ Send data within a topic. 
        :param `data` - the Python object to send. Must be possible to encode into JSON."""

        return self._talk(data)

    def iterator(self):
        """ Get the async iterator used to get data from OpenSpace. """

        return self._iterator

    def cancel(self):
        """ Cancel the topic. """

        return self._cancel()