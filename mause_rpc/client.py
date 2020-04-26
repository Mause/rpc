import logging
from concurrent.futures import Future
from dataclasses import dataclass, field
from functools import partial
from threading import Thread
from typing import Dict
from uuid import uuid4

import dill
from pika import BasicProperties, BlockingConnection
from pika.adapters.blocking_connection import BlockingChannel

logging.getLogger("pika").setLevel(logging.WARN)


@dataclass
class Client:
    server_queue: str
    conn: BlockingConnection
    channel: BlockingChannel
    timeout: int = field(default=10)
    _waiting: Dict[str, Future] = field(default_factory=dict)

    def __post_init__(self):
        self.channel.basic_consume("amq.rabbitmq.reply-to", self.recieve, auto_ack=True)

    def call(self, method, *args, **kwargs):
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
                properties=BasicProperties(reply_to="amq.rabbitmq.reply-to"),
            )
        )
        return f.result(timeout=self.timeout)

    def __getattr__(self, method):
        return partial(self.call, method)

    def recieve(self, ch, method_frame, properties, body):
        body = dill.loads(body)
        f = self._waiting.pop(body["key"])
        if "body" in body:
            f.set_result(body["body"])
        elif "exception" in body:
            f.set_exception(body["exception"])
        else:
            raise RuntimeError()


def get_client(server_queue: str, server_connection_parameters, timeout=10) -> Client:
    conn = BlockingConnection(server_connection_parameters)
    channel = conn.channel()

    t = Thread(target=channel.start_consuming)
    t.daemon = True
    t.start()

    return Client(server_queue, conn, channel, timeout)
