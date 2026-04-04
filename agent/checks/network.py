"""
Сетевые проверки
"""
import socket
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def check_port(host: str, port: int, timeout: int = 3) -> Dict[str, Any]:
    """Проверка доступности порта"""
    result = {
        "host": host,
        "port": port,
        "accessible": False,
        "error": None
    }

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result["accessible"] = sock.connect_ex((host, port)) == 0
        sock.close()
    except socket.gaierror:
        result["error"] = f"Cannot resolve hostname: {host}"
    except socket.timeout:
        result["error"] = f"Connection timeout to {host}:{port}"
    except Exception as e:
        result["error"] = str(e)

    return result


def get_network_info() -> Dict[str, Any]:
    """Сбор сетевой информации"""
    info = {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "interfaces": {},
    }

    if PSUTIL_AVAILABLE:
        for iface_name, addrs in psutil.net_if_addrs().items():
            info["interfaces"][iface_name] = {
                "addresses": [],
                "status": "up" if iface_name in psutil.net_if_stats() and psutil.net_if_stats()[
                    iface_name].isup else "down"
            }

            for addr in addrs:
                addr_info = {
                    "address": addr.address,
                    "family": str(addr.family),
                    "netmask": addr.netmask,
                }
                info["interfaces"][iface_name]["addresses"].append(addr_info)

    return info


def check_ports_batch(hosts_ports: List[tuple], timeout: int = 3) -> List[Dict]:
    """Пакетная проверка портов"""
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(check_port, host, port, timeout): (host, port)
            for host, port in hosts_ports
        }

        for future in as_completed(futures):
            results.append(future.result())

    return results