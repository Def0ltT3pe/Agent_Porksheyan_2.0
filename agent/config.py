# config.py (исправленный)

import os
import logging

class Config:
    API_URL = "http://127.0.0.1:8000"

    AGENT_NAME = "agent-1"
    AGENT_TOKEN = None  # сначала None!

    HEARTBEAT_INTERVAL = 5
    TASK_POLL_INTERVAL = 3

    MAX_CONCURRENT_TASKS = 2
    TASK_TIMEOUT = 30

    API_TIMEOUT = 5
    API_RETRIES = 3

    DEBUG_MODE = True
    LOG_HEARTBEAT = True
    LOG_TASK_DETAILS = True

    STANDALONE_MODE = False
    ONESHOT_MODE = False

    AGENT_VERSION = "1.0"

    AGENT_GROUP = "default"
    AGENT_TAGS = []
    AGENT_DESCRIPTION = "Test agent"

    # ДОБАВЬТЕ ЭТУ СТРОКУ:
    LOG_LEVEL = "DEBUG" if DEBUG_MODE else "INFO"

    def validate(self):
        return True

    def setup_logging(self):
        """Настройка логирования"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))

        if self.DEBUG_MODE:
            file_handler = logging.FileHandler('agent.log', encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format))
            logging.basicConfig(
                level=getattr(logging, self.LOG_LEVEL),
                handlers=[console_handler, file_handler]
            )
        else:
            logging.basicConfig(
                level=getattr(logging, self.LOG_LEVEL),
                handlers=[console_handler]
            )

    def display(self):
        print("=== CONFIG ===")
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                print(f"{key}: {value}")

config = Config()