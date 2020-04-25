from unittest.mock import MagicMock

import dill
from pika import BlockingConnection
from pika.adapters.blocking_connection import BlockingChannel

from mause_rpc.client import Client


def test_init():
    conn = MagicMock(
        spec=BlockingConnection, add_callback_threadsafe=lambda func: func()
    )
    ch = MagicMock(
        spec=BlockingChannel,
        basic_publish=lambda body, **kwargs: client._waiting[
            dill.loads(body)["key"]
        ].set_result("heyo"),
    )
    client: Client = Client("", conn, ch)

    assert client.hello_world("hi") == 'heyo'
