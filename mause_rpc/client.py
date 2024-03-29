'''
A client for a remote procedure call server.
'''

import logging
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from functools import partial
from threading import Thread
from typing import Any, Callable, Dict, Optional, TypeVar
from uuid import uuid4

import dill
from pika import BasicProperties, BlockingConnection
from pika.adapters.blocking_connection import BlockingChannel
from pika.connection import Parameters
from pika.frame import Method
from retry import retry

logging.getLogger("pika").setLevel(logging.WARN)
logger = logging.getLogger(__name__)

REPLY_TO = "amq.rabbitmq.reply-to"
T = TypeVar('T')


@dataclass
class Client:
    '''
    A client for a remote procedure call server.
    '''

    server_queue: str
    timeout: int
    connection_parameters: Parameters
    _thread: Optional[Thread] = None
    conn: Optional[BlockingConnection] = None
    channel: Optional[BlockingChannel] = None
    _waiting: Dict[str, Future] = field(default_factory=dict)

    def worker(self) -> None:
        assert self.channel

        time.sleep(1.5)
        logger.debug('starting worker listening on %s', self.server_queue)
        try:
            self.channel.start_consuming()
        except Exception:
            logger.exception('worker died')
            self.connect()

    def connect(self) -> 'Client':
        '''
        Connect to the server.
        '''
        self.conn = BlockingConnection(self.connection_parameters)
        self.channel = self.conn.channel()

        self._thread = t = Thread(target=self.worker)
        t.daemon = True
        t.start()

        self.channel.basic_consume(REPLY_TO, self.recieve, auto_ack=True)

        return self

    def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        '''
        Call a remote method.
        '''
        assert self.conn and self.channel

        f: Future = Future()
        key = uuid4().hex
        self._waiting[key] = f
        self.conn.add_callback_threadsafe(
            lambda: self.channel.basic_publish(
                exchange="",
                routing_key=self.server_queue,
                body=dill.dumps(
                    {"method": method, "args": args, "kwargs": kwargs, "key": key}
                ),
                properties=BasicProperties(reply_to=REPLY_TO),
            )
        )
        return f.result(timeout=self.timeout)

    def __getattr__(self, method: str) -> Callable:
        return partial(self.call, method)

    def recieve(
        self,
        ch: BlockingChannel,
        method_frame: Method,
        properties: BasicProperties,
        _body: str,
    ) -> None:
        body = dill.loads(_body)
        f = self._waiting.pop(body["key"])
        if "body" in body:
            f.set_result(body["body"])
        elif "exception" in body:
            f.set_exception(body["exception"])
        else:
            raise RuntimeError()


def get_client(
    server_queue: str, connection_parameters: Parameters, timeout: int = 10
) -> Client:
    '''
    Get a client for a remote procedure call server.
    '''
    return Client(server_queue, timeout, connection_parameters).connect()
