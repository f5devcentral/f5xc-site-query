"""
authors: cklewar
"""

from types import NotImplementedType
from typing import Optional, List, Any


class BIOS:
    vendor: str
    version: str
    date: str

    def __init__(self, vendor: str, version: str, date: str) -> None:
        self.vendor = vendor
        self.version = version
        self.date = date


class Board:
    name: Optional[str]
    vendor: str
    version: str
    serial: str
    asset_tag: Optional[str]
    type: Optional[int]

    def __init__(self, name: Optional[str], vendor: str, version: str, serial: str, asset_tag: Optional[str], type: Optional[int]) -> None:
        self.name = name
        self.vendor = vendor
        self.version = version
        self.serial = serial
        self.asset_tag = asset_tag
        self.type = type


class CPU:
    vendor: str
    model: str
    speed: int
    cache: int
    cpus: int
    cores: int
    threads: int
    flags: str

    def __init__(self, vendor: str, model: str, speed: int, cache: int, cpus: int, cores: int, threads: int, flags: str) -> None:
        self.vendor = vendor
        self.model = model
        self.speed = speed
        self.cache = cache
        self.cpus = cpus
        self.cores = cores
        self.threads = threads
        self.flags = flags

    def __eq__(self, other) -> bool | NotImplementedType:
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.cpus == other.cpus and self.cores == other.cores and self.threads == other.threads and self.speed == other.speed


class Kernel:
    release: str
    version: str
    architecture: str

    def __init__(self, release: str, version: str, architecture: str) -> None:
        self.release = release
        self.version = version
        self.architecture = architecture


class Memory:
    type: str
    speed: int
    size_mb: int

    def __init__(self, type: str, speed: int, size_mb: int) -> None:
        self.type = type
        self.speed = speed
        self.size_mb = size_mb

    def __eq__(self, other) -> bool | NotImplementedType:
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.size_mb == other.size_mb and self.size_mb == other.size_mb


class Network:
    name: str
    driver: str
    ip_address: List[str]
    mac_address: str
    port: str
    speed: int
    link_quality: str
    link_type: str

    def __init__(self, name: str, driver: str, ip_address: List[str], mac_address: str, port: str, speed: int, link_quality: str, link_type: str) -> None:
        self.name = name
        self.driver = driver
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.port = port
        self.speed = speed
        self.link_quality = link_quality
        self.link_type = link_type

    def __eq__(self, other) -> bool | NotImplementedType:
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.speed == other.speed and self.port == other.port and self.link_type == other.link_type


class OS:
    name: str
    vendor: str
    version: str
    release: str
    architecture: str

    def __init__(self, name: str, vendor: str, version: str, release: str, architecture: str) -> None:
        self.name = name
        self.vendor = vendor
        self.version = version
        self.release = release
        self.architecture = architecture

    def __eq__(self, other) -> bool | NotImplementedType:
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.architecture == other.architecture


class Storage:
    name: str
    driver: str
    vendor: str
    model: str
    serial: str
    size_gb: int

    def __init__(self, name: str, driver: str, vendor: str, model: str, serial: str, size_gb: int) -> None:
        self.name = name
        self.driver = driver
        self.vendor = vendor
        self.model = model
        self.serial = serial
        self.size_gb = size_gb

    def __eq__(self, other) -> bool | NotImplementedType:
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.size_gb == other.size_gb


class HwInfo:
    os: OS
    product: Board
    board: Board
    chassis: Board
    bios: BIOS
    cpu: CPU
    memory: Memory
    storage: List[Storage]
    network: List[Network]
    kernel: Kernel
    usb: List[Any]
    gpu: None
    numa_nodes: int

    def __init__(self, os: OS, product: Board, board: Board, chassis: Board, bios: BIOS, cpu: CPU, memory: Memory, storage: List[Storage], network: List[Network], kernel: Kernel, usb: List[Any], gpu: None, numa_nodes: int) -> None:
        self.os = os
        self.product = product
        self.board = board
        self.chassis = chassis
        self.bios = bios
        self.cpu = cpu
        self.memory = memory
        self.storage = storage
        self.network = network
        self.kernel = kernel
        self.usb = usb
        self.gpu = gpu
        self.numa_nodes = numa_nodes

    def __eq__(self, other) -> dict[str, bool] | NotImplementedType:
        if not isinstance(other, type(self)):
            return NotImplemented

        info = {
            "os": self.os == other.os,
            "cpu": self.cpu == other.cpu,
            "memory": self.memory == other.memory,
            "storage": self.storage == other.storage,
            "network": [(n_self == n_other) for n_self, n_other in zip(self.network, other.network)]
        }

        return info
