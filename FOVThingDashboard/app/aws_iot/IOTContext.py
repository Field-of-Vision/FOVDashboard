from awscrt import io
from dataclasses import dataclass
from typing import Optional


@dataclass
class IOTCredentials:
    cert_path: str
    client_id: str
    endpoint: str
    priv_key_path: str
    ca_path: str

    port: int = 8883
    region: str = "eu-west-1"


class IOTContext:
    client_bootstrap: io.ClientBootstrap
    event_loop_group: io.EventLoopGroup
    host_resolver: io.DefaultHostResolver

    def __init__(self):
        self.event_loop_group = io.EventLoopGroup(1)  # https://awslabs.github.io/aws-crt-python/api/io.html#awscrt.io.EventLoopGroup
        self.host_resolver = io.DefaultHostResolver(self.event_loop_group)  # https://awslabs.github.io/aws-crt-python/api/io.html#awscrt.io.ClientBootstrap
        self.client_bootstrap = io.ClientBootstrap(self.event_loop_group, self.host_resolver)  # https://awslabs.github.io/aws-crt-python/api/io.html#awscrt.io.ClientBootstrap