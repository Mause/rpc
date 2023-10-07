'''
A simple RPC server that uses RabbitMQ as a message broker.
'''

import logging
import socket
from dataclasses import dataclass, field
from functools import partial
from typing import Callable, Dict, Optional, TypeVar, overload

import dill
import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.connection import Parameters
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker
from pika.frame import Method
from retry import retry

logging.basicConfig(level=logging.INFO)
logging.getLogger("pika").setLevel(logging.WARN)

T = TypeVar('T')


@dataclass
class Server:
    '''
    A simple RPC server that uses RabbitMQ as a message broker.
    '''

    server_queue: str
    connection_params: Parameters
    server_name: Optional[str] = None
    _methods: Dict[str, Callable] = field(default_factory=dict)

    @overload
    def register(self, method: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        '''
        Register a method to be called by the server.

        Uses the given string as the RPC method name.
        '''
        ...

    @overload
    def register(self, method: Callable[..., T]) -> Callable[..., T]:
        '''
        Register a method to be called by the server.

        Uses the method name as the RPC method name.
        '''
        ...

    def register(self, method):  # type: ignore
        if isinstance(method, str):
            return partial(self._register, method)
        else:
            return self._register(method.__name__, method)

    def _register(self, name: str, method: Callable) -> Callable:
        self._methods[name] = method
        return method

    @retry(socket.gaierror, delay=10, jitter=3)
    @retry(ChannelClosedByBroker, delay=10, jitter=3)
    @retry(AMQPConnectionError, delay=5, jitter=3)
    def serve(self) -> None:
        '''
        Start the server and wait for requests.
        '''

        with pika.BlockingConnection(self.connection_params) as conn:
            channel = conn.channel()

            channel.queue_declare(
                queue=self.server_queue, exclusive=True, auto_delete=True
            )
            channel.basic_consume(
                self.server_queue,
                self.on_server_rx_rpc_request,
                consumer_tag=self.server_name,
            )
            logging.info("Ready, waiting on work on %s", self.server_queue)
            channel.start_consuming()

    def on_server_rx_rpc_request(
        self,
        ch: BlockingChannel,
        method_frame: Method,
        properties: Parameters,
        _body: str,
    ) -> None:
        body = dill.loads(_body)
        logging.info("RPC Server got request: %s", body)

        res = {"key": body["key"]}

        try:
            res["body"] = self._methods[body["method"]](*body["args"], **body["kwargs"])
        except Exception as e:
            logging.exception("Call to %s caused exception", body["method"])
            res["exception"] = e

        ch.basic_publish("", routing_key=properties.reply_to, body=dill.dumps(res))

        ch.basic_ack(delivery_tag=method_frame.delivery_tag)
