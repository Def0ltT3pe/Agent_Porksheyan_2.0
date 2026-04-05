#!/usr/bin/env python3
"""
Агент для выполнения диагностических задач
"""

import os
import sys
import json
import time
import signal
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, Future

import requests
import psutil
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from colorama import init, Fore, Style

from checks.system_info import get_system_info, get_host_info
from checks.network import check_port, get_network_info
from checks.commands import run_safe_command
from config import config

init(autoreset=True)
config.setup_logging()
logger = logging.getLogger(__name__)


@dataclass
class Task:
    id: int
    type: str
    payload: Dict[str, Any]
    status: str = "pending"


class Agent:
    def __init__(self):
        self.api_url = config.API_URL
        self.agent_name = config.AGENT_NAME
        self.agent_token = config.AGENT_TOKEN
        self.heartbeat_interval = config.HEARTBEAT_INTERVAL
        self.task_poll_interval = config.TASK_POLL_INTERVAL
        self.max_concurrent_tasks = config.MAX_CONCURRENT_TASKS
        self.task_timeout = config.TASK_TIMEOUT

        if not config.validate():
            logger.error("Ошибка валидации конфигурации")
            sys.exit(1)

        self.running = True
        self.tasks_queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_tasks)
        self.active_tasks: Dict[int, Future] = {}

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self._print_banner()

    def _print_banner(self):
        print(f"""
{Fore.CYAN}{'=' * 60}
{Fore.GREEN} Агент диагностики инфраструктуры v{config.AGENT_VERSION}
{Fore.YELLOW} Имя: {Style.BRIGHT}{self.agent_name}
{Fore.YELLOW}API: {self.api_url}
{Fore.YELLOW}Макс. задач: {self.max_concurrent_tasks}
{Fore.YELLOW}Heartbeat: {self.heartbeat_interval}с
{Fore.YELLOW}Опрос задач: {self.task_poll_interval}с
{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}
        """)
        if config.DEBUG_MODE:
            config.display()

    def _signal_handler(self, signum, frame):
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        self.running = False
        self.executor.shutdown(wait=True)
        sys.exit(0)

    def _save_token_to_env(self):
        env_path = '.env'
        token_line = f'AGENT_TOKEN={self.agent_token}'
        lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
        token_updated = False
        for i, line in enumerate(lines):
            if line.startswith('AGENT_TOKEN='):
                lines[i] = f'{token_line}\n'
                token_updated = True
                break
        if not token_updated:
            lines.append(f'{token_line}\n')
        with open(env_path, 'w') as f:
            f.writelines(lines)
        logger.info("Токен сохранён в .env файл")

    @retry(stop=stop_after_attempt(config.API_RETRIES), wait=wait_exponential(multiplier=1, min=2, max=30))
    def register(self) -> bool:
        # Если токен уже есть – пробуем использовать его (проверка через heartbeat не нужна, просто отправим heartbeat позже)
        if self.agent_token:
            logger.info(f"Агент уже имеет токен: {self.agent_token[:10]}...")
            # Не проверяем валидность сразу, а просто возвращаем True.
            # В heartbeat_worker при неудаче вызовем повторную регистрацию.
            return True

        logger.info(f"Регистрация агента '{self.agent_name}'...")
        host_info = get_host_info()
        response = requests.post(
            f"{self.api_url}/agents/register",
            json={
                "name": self.agent_name,
                "hostname": host_info['hostname'],
                "ip_addresses": host_info['ip_addresses'],
                "os_info": host_info['os_info'],
                "group": config.AGENT_GROUP,
                "tags": config.AGENT_TAGS,
                "description": config.AGENT_DESCRIPTION
            },
            timeout=config.API_TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            self.agent_token = data['token']
            self._save_token_to_env()
            logger.info(f"Агент успешно зарегистрирован! Токен: {self.agent_token[:20]}...")
            return True
        else:
            logger.error(f"Ошибка регистрации: {response.status_code} - {response.text}")
            return False

    @retry(stop=stop_after_attempt(config.API_RETRIES))
    def send_heartbeat(self) -> bool:
        try:
            response = requests.post(
                f"{self.api_url}/agents/heartbeat",
                headers={"X-Agent-Token": self.agent_token},
                json={"timestamp": datetime.now().isoformat(), "status": "running", "active_tasks": len(self.active_tasks)},
                timeout=config.API_TIMEOUT
            )
            if config.LOG_HEARTBEAT:
                logger.debug("Heartbeat отправлен")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
            return False

    @retry(stop=stop_after_attempt(config.API_RETRIES))
    def get_task(self) -> Optional[Task]:
        try:
            response = requests.get(
                f"{self.api_url}/agents/tasks/next",
                headers={"X-Agent-Token": self.agent_token},
                timeout=config.API_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                if data and data.get("id"):
                    logger.info(f"Получена новая задача #{data['id']} типа '{data['type']}'")
                    return Task(id=data['id'], type=data['type'], payload=data.get('payload', {}))
                else:
                    logger.debug("Нет новых задач (пустой ответ)")
            else:
                logger.warning(f"Ошибка получения задачи: статус {response.status_code}")
        except Exception as e:
            logger.error(f"Ошибка при получении задачи: {e}")
        return None

    def send_log(self, task_id: int, log_message: str, level: str = "INFO"):
        pass

    def log_and_send(self, task_id: int, message: str, level: str = "INFO"):
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
        # Не отправляем отдельный запрос, так как он не реализован на сервере.

    def execute_task(self, task: Task) -> Dict[str, Any]:
        logger.info(f"Выполнение задачи #{task.id} типа '{task.type}'")
        try:
            if task.type == "system_info":
                result = get_system_info()
            elif task.type == "host_info":
                result = get_host_info()
            elif task.type == "check_port":
                result = check_port(task.payload.get('host'), task.payload.get('port'))
            elif task.type == "network_info":
                result = get_network_info()
            elif task.type == "run_command":
                timeout = task.payload.get('timeout', self.task_timeout)
                result = run_safe_command(task.payload.get('command'), timeout=timeout)
            elif task.type == "check_services":
                result = self._check_services(task.payload.get('services', []))
            elif task.type == "batch_check":
                result = self._execute_batch_checks(task.payload.get('checks', []))
            else:
                result = {"error": f"Неизвестный тип задачи: {task.type}", "success": False}
            result["success"] = True
            result["executed_at"] = datetime.now().isoformat()
            result["agent_name"] = self.agent_name
            result["agent_version"] = config.AGENT_VERSION
            if config.LOG_TASK_DETAILS:
                logger.info(f"Задача #{task.id} выполнена успешно")
            return result
        except Exception as e:
            logger.error(f"Ошибка выполнения задачи #{task.id}: {e}")
            return {"success": False, "error": str(e), "executed_at": datetime.now().isoformat()}

    def _check_services(self, services: List[str]) -> Dict[str, Any]:
        results = {}
        for service in services:
            try:
                import subprocess
                result = subprocess.run(["systemctl", "is-active", service], capture_output=True, text=True, timeout=10)
                results[service] = {"status": result.stdout.strip(), "active": result.returncode == 0}
            except:
                results[service] = {"status": "unknown", "active": False, "error": "Cannot check service"}
        return {"services": results}

    def _execute_batch_checks(self, checks: List[Dict]) -> Dict[str, Any]:
        results = []
        for check in checks:
            check_type = check.get('type')
            if check_type == "check_port":
                result = check_port(check.get('host'), check.get('port'))
            elif check_type == "run_command":
                timeout = check.get('timeout', self.task_timeout)
                result = run_safe_command(check.get('command'), timeout=timeout)
            else:
                result = {"error": f"Unknown check type: {check_type}"}
            results.append({"check": check, "result": result})
        return {"batch_results": results, "total_checks": len(checks)}

    @retry(stop=stop_after_attempt(config.API_RETRIES), wait=wait_exponential(multiplier=1, min=1, max=10))
    def submit_result(self, task_id: int, result: Dict[str, Any]) -> bool:
        try:
            response = requests.post(
                f"{self.api_url}/tasks/{task_id}/result",
                headers={"X-Agent-Token": self.agent_token},
                json={
                    "status": "completed" if result.get("success") else "failed",
                    "result": result,
                    "logs": result.get("logs", ""),
                    "agent_name": self.agent_name
                },
                timeout=config.API_TIMEOUT
            )
            if response.status_code == 200:
                logger.info(f"📤 Результат задачи #{task_id} успешно отправлен")
                return True
            else:
                error_msg = f"Ошибка отправки результата: статус {response.status_code} - {response.text}"
                logger.error(f"{error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Критическая ошибка при отправке результата задачи #{task_id}: {e}")
            raise

    def task_worker(self, task: Task):
        try:
            self._update_task_status(task.id, "running")
            result = self.execute_task(task)
            self.submit_result(task.id, result)
        except Exception as e:
            logger.error(f"Критическая ошибка в задаче #{task.id}: {e}")
            try:
                self.submit_result(task.id, {"success": False, "error": str(e)})
            except:
                logger.error(f"Не удалось отправить даже сообщение об ошибке для задачи #{task.id}")
        finally:
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]

    def _update_task_status(self, task_id: int, status: str):
        try:
            requests.patch(
                f"{self.api_url}/tasks/{task_id}",
                headers={"X-Agent-Token": self.agent_token},
                json={"status": status},
                timeout=config.API_TIMEOUT
            )
        except:
            pass

    def process_tasks(self):
        logger.info("Запуск цикла обработки задач...")
        while self.running:
            try:
                if len(self.active_tasks) >= self.max_concurrent_tasks:
                    logger.debug(f"Достигнут лимит параллельных задач ({self.max_concurrent_tasks})")
                    time.sleep(0.5)
                    continue
                task = self.get_task()
                if task:
                    logger.info(f"📥 Задача #{task.id} ({task.type}) получена и отправлена на выполнение")
                    future = self.executor.submit(self.task_worker, task)
                    self.active_tasks[task.id] = future
                else:
                    time.sleep(self.task_poll_interval)
            except Exception as e:
                logger.error(f"Ошибка в цикле обработки задач: {e}")
                time.sleep(1)

    def heartbeat_worker(self):
        logger.info("Запуск heartbeat worker...")
        while self.running:
            try:
                if self.agent_token:
                    success = self.send_heartbeat()
                    if not success:
                        logger.warning("⚠️ Heartbeat не доставлен, пробуем перерегистрацию")
                        # Если токен невалиден, регистрируемся заново (сервер обновит токен)
                        self.agent_token = None  # сбрасываем старый токен
                        if self.register():
                            logger.info("Перерегистрация успешна")
                        else:
                            logger.error("Не удалось перерегистрироваться")
                else:
                    logger.warning("Нет токена для heartbeat, регистрируемся")
                    self.register()
            except Exception as e:
                logger.error(f"Ошибка в heartbeat worker: {e}")
            time.sleep(self.heartbeat_interval)

    def run(self):
        logger.info("Запуск агента...")
        if config.STANDALONE_MODE:
            logger.warning("Режим STANDALONE: регистрация на сервере не выполняется")
        else:
            if not self.register():
                logger.error("Не удалось зарегистрировать агент")
                sys.exit(1)

        if not config.STANDALONE_MODE:
            heartbeat_thread = threading.Thread(target=self.heartbeat_worker, daemon=True)
            heartbeat_thread.start()

        if config.ONESHOT_MODE:
            logger.info("Режим ONESHOT: выполнение одной задачи и выход")
            task = self.get_task()
            if task:
                self.task_worker(task)
            else:
                logger.info("Нет задач для выполнения")
            return

        self.process_tasks()


def main():
    if config.DEBUG_MODE:
        print(f"{Fore.YELLOW}РЕЖИМ ОТЛАДКИ ВКЛЮЧЁН{Style.RESET_ALL}")
    agent = Agent()
    try:
        agent.run()
    except KeyboardInterrupt:
        logger.info("Агент остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()