# config.py
import os
import logging
from dotenv import load_dotenv

# Загружаем переменные из .env файла (если есть)
load_dotenv()

class Config:
    # API сервера
    API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

    # Агент
    AGENT_NAME = os.getenv("AGENT_NAME", "agent-1")
    AGENT_TOKEN = os.getenv("AGENT_TOKEN", None)  # загружается из .env
    AGENT_VERSION = "1.0"
    AGENT_GROUP = os.getenv("AGENT_GROUP", "default")
    AGENT_TAGS = os.getenv("AGENT_TAGS", "").split(",") if os.getenv("AGENT_TAGS") else []
    AGENT_DESCRIPTION = os.getenv("AGENT_DESCRIPTION", "Test agent")

    # Интервалы
    HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "1"))
    TASK_POLL_INTERVAL = float(os.getenv("TASK_POLL_INTERVAL", "0.5"))

    # Производительность
    MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "4"))
    TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", "30"))

    # API параметры
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "5"))
    API_RETRIES = int(os.getenv("API_RETRIES", "3"))

    # Режимы работы
    DEBUG_MODE = os.getenv("DEBUG_MODE", "True").lower() == "true"
    LOG_HEARTBEAT = os.getenv("LOG_HEARTBEAT", "True").lower() == "true"
    LOG_TASK_DETAILS = os.getenv("LOG_TASK_DETAILS", "True").lower() == "true"
    STANDALONE_MODE = os.getenv("STANDALONE_MODE", "False").lower() == "true"
    ONESHOT_MODE = os.getenv("ONESHOT_MODE", "False").lower() == "true"

    # Уровень логирования (автоматически)
    LOG_LEVEL = "DEBUG" if DEBUG_MODE else "INFO"

    def validate(self):
        """Проверка обязательных настроек"""
        if not self.API_URL:
            logging.error("API_URL не задан")
            return False
        return True

    def setup_logging(self):
        """Настройка логирования"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        handlers = [logging.StreamHandler()]

        if self.DEBUG_MODE:
            file_handler = logging.FileHandler('agent.log', encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)

        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL),
            format=log_format,
            handlers=handlers
        )

    def display(self):
        """Отладка: вывод всех настроек"""
        print("=== CONFIG ===")
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                print(f"{key}: {value}")

# Глобальный экземпляр конфига
config = Config()