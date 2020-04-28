from unittest.mock import MagicMock, patch

import dill
from mause_rpc.client import Client
from mause_rpc.server import Server
from pika import BasicProperties, BlockingConnection
from pika.adapters.blocking_connection import BlockingChannel


def test_client():
    conn = MagicMock(
        spec=BlockingConnection, add_callback_threadsafe=lambda func: func()
    )
    ch = MagicMock(
        spec=BlockingChannel,
        basic_publish=lambda body, **kwargs: client._waiting[
            dill.loads(body)['key']
        ].set_result('heyo'),
    )
    client: Client = Client('', conn, ch, 10, MagicMock())

    assert client.hello_world('hi') == 'heyo'


@patch('mause_rpc.server.pika.BlockingConnection', spec=BlockingConnection)
def test_server(bc):
    server = Server('', '')

    @server.register
    def hello(name):
        return 'hello ' + name

    ch = MagicMock(spec=BlockingChannel)

    server.on_server_rx_rpc_request(
        ch=ch,
        method_frame=MagicMock(),
        properties=BasicProperties(reply_to='reply_to'),
        body=dill.dumps(
            {'key': 'key', 'args': ('mark',), 'kwargs': {}, 'method': 'hello'}
        ),
    )

    call = ch.basic_publish.mock_calls[0]
    assert dill.loads(call.kwargs['body']) == {'key': 'key', 'body': 'hello mark'}


def test_register():
    server = Server('', MagicMock())

    @server.register('hello')
    def world():
        ...

    @server.register
    def help():
        ...

    assert set(server._methods) == {'hello', 'help'}
