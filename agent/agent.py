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
from tenacity import retry, stop_after_attempt, wait_exponential
from colorama import init, Fore, Style

# Импорт модулей проверок
from checks.system_info import get_system_info, get_host_info
from checks.network import check_port, get_network_info
from checks.commands import run_safe_command

# Импорт конфигурации
from config import config

# Инициализация colorama для Windows
init(autoreset=True)

# Настройка логирования через config
config.setup_logging()
logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Модель задачи"""
    id: int
    type: str
    payload: Dict[str, Any]
    status: str = "pending"


class Agent:
    """Основной класс агента"""

    def __init__(self):
        # Загружаем настройки из config
        self.api_url = config.API_URL
        self.agent_name = config.AGENT_NAME
        self.agent_token = config.AGENT_TOKEN
        self.heartbeat_interval = config.HEARTBEAT_INTERVAL
        self.task_poll_interval = config.TASK_POLL_INTERVAL
        self.max_concurrent_tasks = config.MAX_CONCURRENT_TASKS
        self.task_timeout = config.TASK_TIMEOUT

        # Проверяем настройки
        if not config.validate():
            logger.error("Ошибка валидации конфигурации")
            sys.exit(1)

        self.running = True
        self.tasks_queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_tasks)
        self.active_tasks: Dict[int, Future] = {}

        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._print_banner()

    def _print_banner(self):
        """Вывод красивого баннера при старте"""
        print(f"""
{Fore.CYAN}{'=' * 60}
{Fore.GREEN}🐍 Агент диагностики инфраструктуры v{config.AGENT_VERSION}
{Fore.YELLOW}📡 Имя: {Style.BRIGHT}{self.agent_name}
{Fore.YELLOW}🔗 API: {self.api_url}
{Fore.YELLOW}⚡ Макс. задач: {self.max_concurrent_tasks}
{Fore.YELLOW}💓 Heartbeat: {self.heartbeat_interval}с
{Fore.YELLOW}⏱️  Опрос задач: {self.task_poll_interval}с
{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}
        """)

        # Показываем настройки в DEBUG режиме
        if config.DEBUG_MODE:
            config.display()

    def _signal_handler(self, signum, frame):
        """Обработка сигналов завершения"""
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        self.running = False
        self.executor.shutdown(wait=True)
        sys.exit(0)

    def _save_token_to_env(self):
        """Сохраняет токен в файл .env"""
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

        logger.info("💾 Токен сохранён в .env файл")

    @retry(
        stop=stop_after_attempt(config.API_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30)
    )
    def register(self) -> bool:
        """Регистрация агента в системе"""
        if self.agent_token:
            logger.info(f"Агент уже зарегистрирован с токеном: {self.agent_token[:10]}...")
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

            logger.info(f"✅ Агент успешно зарегистрирован!")
            logger.info(f"🔑 Токен: {self.agent_token[:20]}...")
            return True
        else:
            logger.error(f"❌ Ошибка регистрации: {response.status_code} - {response.text}")
            return False

    @retry(stop=stop_after_attempt(config.API_RETRIES))
    def send_heartbeat(self) -> bool:
        """Отправка heartbeat для подтверждения активности"""
        try:
            response = requests.post(
                f"{self.api_url}/agents/heartbeat",
                headers={"X-Agent-Token": self.agent_token},
                json={
                    "timestamp": datetime.now().isoformat(),
                    "status": "running",
                    "active_tasks": len(self.active_tasks)
                },
                timeout=config.API_TIMEOUT
            )

            if config.LOG_HEARTBEAT:
                logger.debug("💓 Heartbeat отправлен")

            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
            return False

    @retry(stop=stop_after_attempt(config.API_RETRIES))
    def get_task(self) -> Optional[Task]:
        """Получение задачи от сервера"""
        try:
            response = requests.get(
                f"{self.api_url}/agents/tasks/next",
                headers={"X-Agent-Token": self.agent_token},
                timeout=config.API_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                if data:
                    logger.info(f"📨 Получена новая задача #{data['id']}: {data['type']}")
                    return Task(
                        id=data['id'],
                        type=data['type'],
                        payload=data.get('payload', {})
                    )
            elif response.status_code == 204:
                return None
            else:
                logger.warning(f"Ошибка получения задачи: {response.status_code}")

        except Exception as e:
            logger.error(f"Ошибка при получении задачи: {e}")

        return None

    def send_log(self, task_id: int, log_message: str, level: str = "INFO"):
        """Отправка лога на сервер"""
        try:
            response = requests.post(
                f"{self.api_url}/tasks/{task_id}/logs",
                headers={"X-Agent-Token": self.agent_token},
                json={
                    "logs": f"[{level}] {log_message}",
                    "timestamp": datetime.now().isoformat()
                },
                timeout=config.API_TIMEOUT
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Не удалось отправить лог: {e}")
            return False

    def log_and_send(self, task_id: int, message: str, level: str = "INFO"):
        """Логирует в консоль и отправляет на сервер"""
        # Выводим в консоль
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

        # Отправляем на сервер
        self.send_log(task_id, message, level)

    def execute_task(self, task: Task) -> Dict[str, Any]:
        """Выполнение задачи в зависимости от типа"""
        logger.info(f"🔧 Выполнение задачи #{task.id} типа '{task.type}'")

        try:
            if task.type == "system_info":
                result = get_system_info()
            elif task.type == "host_info":
                result = get_host_info()
            elif task.type == "check_port":
                result = check_port(
                    task.payload.get('host'),
                    task.payload.get('port')
                )
            elif task.type == "network_info":
                result = get_network_info()
            elif task.type == "run_command":
                # Используем timeout из конфига или из задачи
                timeout = task.payload.get('timeout', self.task_timeout)
                result = run_safe_command(
                    task.payload.get('command'),
                    timeout=timeout
                )
            elif task.type == "check_services":
                result = self._check_services(task.payload.get('services', []))
            elif task.type == "batch_check":
                result = self._execute_batch_checks(task.payload.get('checks', []))
            else:
                result = {
                    "error": f"Неизвестный тип задачи: {task.type}",
                    "success": False
                }

            result["success"] = True
            result["executed_at"] = datetime.now().isoformat()
            result["agent_name"] = self.agent_name
            result["agent_version"] = config.AGENT_VERSION

            if config.LOG_TASK_DETAILS:
                logger.info(f"✅ Задача #{task.id} выполнена успешно")
            return result

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения задачи #{task.id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "executed_at": datetime.now().isoformat()
            }

    def _check_services(self, services: List[str]) -> Dict[str, Any]:
        """Проверка статуса сервисов"""
        results = {}
        for service in services:
            try:
                import subprocess
                result = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True, text=True, timeout=10
                )
                results[service] = {
                    "status": result.stdout.strip(),
                    "active": result.returncode == 0
                }
            except:
                results[service] = {
                    "status": "unknown",
                    "active": False,
                    "error": "Cannot check service"
                }
        return {"services": results}

    def _execute_batch_checks(self, checks: List[Dict]) -> Dict[str, Any]:
        """Выполнение пакета проверок"""
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

            results.append({
                "check": check,
                "result": result
            })

        return {"batch_results": results, "total_checks": len(checks)}

    def submit_result(self, task_id: int, result: Dict[str, Any]) -> bool:
        """Отправка результата выполнения задачи"""
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
                logger.info(f"📤 Результат задачи #{task_id} отправлен")
                return True
            else:
                logger.error(f"Ошибка отправки результата: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при отправке результата: {e}")
            return False

    def task_worker(self, task: Task):
        """Воркер для выполнения задачи в отдельном потоке"""
        try:
            self._update_task_status(task.id, "running")
            result = self.execute_task(task)
            self.submit_result(task.id, result)
        except Exception as e:
            logger.error(f"Критическая ошибка в задаче #{task.id}: {e}")
            self.submit_result(task.id, {
                "success": False,
                "error": str(e)
            })
        finally:
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]

    def _update_task_status(self, task_id: int, status: str):
        """Обновление статуса задачи на сервере"""
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
        """Основной цикл обработки задач"""
        logger.info("🔄 Запуск цикла обработки задач...")

        while self.running:
            try:
                if len(self.active_tasks) >= self.max_concurrent_tasks:
                    logger.debug(f"Достигнут лимит параллельных задач ({self.max_concurrent_tasks})")
                    time.sleep(1)
                    continue

                task = self.get_task()

                if task:
                    future = self.executor.submit(self.task_worker, task)
                    self.active_tasks[task.id] = future
                    logger.info(f"🚀 Задача #{task.id} запущена. Активных задач: {len(self.active_tasks)}")

                time.sleep(self.task_poll_interval)

            except Exception as e:
                logger.error(f"Ошибка в цикле обработки задач: {e}")
                time.sleep(5)

    def heartbeat_worker(self):
        """Отдельный поток для отправки heartbeat"""
        logger.info("💓 Запуск heartbeat worker...")

        while self.running:
            try:
                if self.agent_token:
                    success = self.send_heartbeat()
                    if not success:
                        logger.warning("⚠️ Heartbeat не доставлен")
                else:
                    logger.warning("Нет токена для heartbeat")
            except Exception as e:
                logger.error(f"Ошибка в heartbeat worker: {e}")

            time.sleep(self.heartbeat_interval)

    def run(self):
        """Запуск агента"""
        logger.info("🚀 Запуск агента...")

        # Режим автономной работы (без регистрации)
        if config.STANDALONE_MODE:
            logger.warning("Режим STANDALONE: регистрация на сервере не выполняется")
        else:
            if not self.register():
                logger.error("Не удалось зарегистрировать агент")
                sys.exit(1)

        # Запускаем heartbeat в отдельном потоке
        if not config.STANDALONE_MODE:
            heartbeat_thread = threading.Thread(target=self.heartbeat_worker, daemon=True)
            heartbeat_thread.start()

        # Режим однократного выполнения
        if config.ONESHOT_MODE:
            logger.info("Режим ONESHOT: выполнение одной задачи и выход")
            task = self.get_task()
            if task:
                self.task_worker(task)
            else:
                logger.info("Нет задач для выполнения")
            return

        # Основной цикл
        self.process_tasks()


def main():
    """Точка входа"""
    # Проверяем режим отладки
    if config.DEBUG_MODE:
        print(f"{Fore.YELLOW}🐛 РЕЖИМ ОТЛАДКИ ВКЛЮЧЁН{Style.RESET_ALL}")

    # Создаём и запускаем агента
    agent = Agent()

    try:
        agent.run()
    except KeyboardInterrupt:
        logger.info("👋 Агент остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()