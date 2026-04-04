"""
Сбор информации о системе
"""
import platform
import socket
from datetime import datetime
from typing import Dict, Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def get_system_info() -> Dict[str, Any]:
    """Детальная информация о системе"""
    info = {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": socket.gethostname(),
        "python_version": platform.python_version()
    }

    if PSUTIL_AVAILABLE:
        # CPU info
        info["cpu"] = {
            "physical_cores": psutil.cpu_count(logical=False),
            "total_cores": psutil.cpu_count(logical=True),
            "percent_usage": psutil.cpu_percent(interval=1),
        }

        # Memory info
        memory = psutil.virtual_memory()
        info["memory"] = {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
            "free": memory.free
        }

        # Disk info
        info["disks"] = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                info["disks"].append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent
                })
            except:
                continue

    return info


def get_host_info() -> Dict[str, Any]:
    """Базовая информация о хосте (для регистрации)"""
    hostname = socket.gethostname()

    # Получаем IP адреса
    ip_addresses = []
    try:
        hostname_ip = socket.gethostbyname(hostname)
        ip_addresses.append(hostname_ip)
    except:
        pass

    # Получаем все IP интерфейсов
    if PSUTIL_AVAILABLE:
        try:
            for interface_name, addresses in psutil.net_if_addrs().items():
                for addr in addresses:
                    if addr.family == socket.AF_INET and addr.address not in ip_addresses:
                        ip_addresses.append(addr.address)
        except:
            pass

    return {
        "hostname": hostname,
        "ip_addresses": ip_addresses,
        "os_info": f"{platform.system()} {platform.release()}",
        "platform": platform.platform()
    }