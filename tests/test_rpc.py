from threading import Thread
from unittest.mock import MagicMock, patch

import dill
from pika import BasicProperties, BlockingConnection
from pika.adapters.blocking_connection import BlockingChannel
from pika.connection import Parameters

from mause_rpc.client import Client, get_client
from mause_rpc.server import Server


def test_combined() -> None:
    rpc_queue = 'rpc_queue'
    rabbitmq_url = None
    server = Server(rpc_queue, rabbitmq_url)

    @server.register
    def hello(name: str) -> str:
        return 'hello ' + name

    Thread(target=server.serve, daemon=True).start()

    client = get_client(rpc_queue, rabbitmq_url)

    assert client.hello('John') == 'hello John'


@patch('mause_rpc.client.BlockingConnection', spec=BlockingConnection)
def test_client(bc: BlockingConnection) -> None:
    bc = bc.return_value
    bc.add_callback_threadsafe.side_effect = lambda func: func()
    bc.channel.return_value = MagicMock(
        spec=BlockingChannel,
        basic_publish=lambda body, **kwargs: client._waiting[
            dill.loads(body)['key']
        ].set_result('heyo'),
    )
    params = MagicMock(spec=Parameters)
    client: Client = Client('', 10, params).connect()

    assert client.hello_world('hi') == 'heyo'


@patch('mause_rpc.server.pika.BlockingConnection', spec=BlockingConnection)
def test_server(bc: BlockingConnection) -> None:
    server = Server('', '')

    @server.register
    def hello(name: str) -> str:
        return 'hello ' + name

    ch = MagicMock(spec=BlockingChannel)

    server.on_server_rx_rpc_request(
        ch=ch,
        method_frame=MagicMock(),
        properties=BasicProperties(reply_to='reply_to'),
        _body=dill.dumps(
            {'key': 'key', 'args': ('mark',), 'kwargs': {}, 'method': 'hello'}
        ),
    )

    call = ch.basic_publish.mock_calls[0]
    assert dill.loads(call.kwargs['body']) == {'key': 'key', 'body': 'hello mark'}


def test_register() -> None:
    server = Server('', MagicMock())

    @server.register('hello')
    def world() -> None: ...

    @server.register
    def help() -> None: ...

    assert set(server._methods) == {'hello', 'help'}
