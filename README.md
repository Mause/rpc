Mause RPC
=========

A dumb as hell rpc implementation built on rabbitmq

Need to write a server?

```py
from mause_rpc.server import Server

rpc_queue = "rpc.queue"
server = Server(rpc_queue, "rabbitmq://...")


@server.register
def hello(name: str) -> str:
    return "hello " + name


@server.register("divide")
def div(a: int, b: int) -> float:
    if b == 0:
        raise ZeroDivisionError()
    return a / b


if __name__ == "__main__":
    server.serve()
```

Need a client?

```py
from mause_rpc.client import get_client

rpc_queue = "rpc.queue"
client = get_client(rpc_queue, "rabbitmq://...")


def test_basic_functionality():
    assert client.hello("mark") == "hello mark"
    assert client.divide(5, 2) == 2.5

    with pytest.raises(ZeroDivisionError):
        client.divide(5, 0)
```
