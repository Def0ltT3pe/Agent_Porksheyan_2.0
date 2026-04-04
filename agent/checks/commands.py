"""
Безопасное выполнение диагностических команд
"""

import subprocess
import shlex
from typing import Dict, Any, List

# Белый список разрешённых команд
ALLOWED_COMMANDS = [
    "df", "free", "uptime", "whoami", "hostname",
    "date", "ps aux", "netstat -tulpn", "ss -tulpn",
    "ip addr", "ifconfig", "ping -c 4", "traceroute"
]

# Чёрный список опасных команд (запрещены)
BLOCKED_COMMANDS = [
    "rm", "dd", "mkfs", "format", "shutdown", "reboot",
    "halt", "poweroff", "kill", "pkill", "killall",
    "chmod", "chown", "passwd", "sudo", "su"
]


def is_command_safe(command: str) -> bool:
    """Проверка безопасности команды"""
    command_lower = command.lower()

    # Проверка чёрного списка
    for blocked in BLOCKED_COMMANDS:
        if blocked in command_lower:
            return False

    # Проверка, что команда начинается с разрешённой
    for allowed in ALLOWED_COMMANDS:
        if command_lower.startswith(allowed.lower().split()[0]):
            return True

    return False


def run_safe_command(command: str, timeout: int = 30, shell: bool = True) -> Dict[str, Any]:
    """Безопасное выполнение команды"""
    result = {
        "command": command,
        "stdout": "",
        "stderr": "",
        "returncode": -1,
        "executed": False,
        "error": None
    }

    # Проверка безопасности
    if not is_command_safe(command):
        result["error"] = f"Command not allowed: {command}"
        return result

    try:
        # Выполнение команды
        if shell:
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                executable="/bin/bash" if not subprocess.__name__ == 'nt' else None
            )
        else:
            args = shlex.split(command)
            process = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout
            )

        result["stdout"] = process.stdout.strip()
        result["stderr"] = process.stderr.strip()
        result["returncode"] = process.returncode
        result["executed"] = True

    except subprocess.TimeoutExpired:
        result["error"] = f"Command timed out after {timeout} seconds"
    except FileNotFoundError:
        result["error"] = f"Command not found: {command}"
    except Exception as e:
        result["error"] = str(e)

    return result


def run_batch_commands(commands: List[str], max_parallel: int = 3) -> List[Dict]:
    """Параллельное выполнение нескольких команд"""
    from concurrent.futures import ThreadPoolExecutor

    results = []

    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = {executor.submit(run_safe_command, cmd): cmd for cmd in commands}

        for future in futures:
            results.append(future.result())

    return results