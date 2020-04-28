import logging
import socket
from dataclasses import dataclass, field
from typing import Callable, Dict

import dill
import pika
from pika import ConnectionParameters
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker
from retry import retry

logging.basicConfig(level=logging.INFO)
logging.getLogger("pika").setLevel(logging.WARN)


@dataclass
class Server:
    server_queue: str
    connection_params: ConnectionParameters
    _methods: Dict[str, Callable] = field(default_factory=dict)

    def register(self, method: Callable):
        self._methods[method.__name__] = method
        return method

    @retry(socket.gaierror, delay=10, jitter=(1, 3))
    @retry(ChannelClosedByBroker, delay=10, jitter=(1, 3))
    @retry(AMQPConnectionError, delay=5, jitter=(1, 3))
    def serve(self):
        with pika.BlockingConnection(self.connection_params) as conn:
            channel = conn.channel()

            channel.queue_declare(
                queue=self.server_queue, exclusive=True, auto_delete=True
            )
            channel.basic_consume(self.server_queue, self.on_server_rx_rpc_request)
            logging.info("Ready, waiting on work on %s", self.server_queue)
            channel.start_consuming()

    def on_server_rx_rpc_request(self, ch, method_frame, properties, body):
        body = dill.loads(body)
        logging.info("RPC Server got request: %s", body)

        res = {"key": body["key"]}

        try:
            res["body"] = self._methods[body["method"]](*body["args"], **body["kwargs"])
        except Exception as e:
            logging.exception("Call to %s caused exception", body["method"])
            res["exception"] = e

        ch.basic_publish("", routing_key=properties.reply_to, body=dill.dumps(res))

        ch.basic_ack(delivery_tag=method_frame.delivery_tag)
