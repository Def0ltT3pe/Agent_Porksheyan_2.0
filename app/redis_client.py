import redis
import json
import os
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Читаем настройки Redis из переменных окружения
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Создаём клиент с обработкой ошибок
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2
    )
    # Проверяем соединение при старте (опционально)
    redis_client.ping()
    logger.info(f"Redis подключён: {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.warning(f"Redis недоступен: {e}. Функции Redis будут работать с ошибками.")
    redis_client = None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=3))
def push_task(agent_id: int, task_id: int, task_type: str, payload: dict) -> None:
    """Поместить задачу в очередь конкретного агента (с повторами при ошибках)"""
    if redis_client is None:
        logger.warning("Redis не доступен, задача не будет помещена в очередь")
        return
    queue_name = f"tasks:{agent_id}"
    task = {
        "id": task_id,
        "type": task_type,
        "payload": payload
    }
    try:
        redis_client.lpush(queue_name, json.dumps(task))
        logger.debug(f"Задача {task_id} добавлена в Redis очередь {queue_name}")
    except Exception as e:
        logger.error(f"Ошибка push_task в Redis: {e}")
        raise


def pop_task(agent_id: int, timeout: int = 2) -> dict | None:
    """Агент забирает задачу из своей очереди (блокирующий вызов)"""
    if redis_client is None:
        logger.warning("Redis не доступен, невозможно получить задачу")
        return None
    queue_name = f"tasks:{agent_id}"
    try:
        result = redis_client.brpop(queue_name, timeout=timeout)
        if result:
            _, task_json = result
            return json.loads(task_json)
    except Exception as e:
        logger.error(f"Ошибка pop_task из Redis: {e}")
    return None


def set_agent_heartbeat(agent_id: int, ttl: int = 30) -> None:
    """Агент сообщает, что жив (храним в Redis)"""
    if redis_client is None:
        return
    try:
        redis_client.set(f"agent:{agent_id}:heartbeat", "1", ex=ttl)
    except Exception as e:
        logger.error(f"Ошибка set_agent_heartbeat: {e}")


def is_agent_alive(agent_id: int) -> bool:
    """Проверить, жив ли агент по Redis"""
    if redis_client is None:
        return False
    try:
        return redis_client.exists(f"agent:{agent_id}:heartbeat") == 1
    except Exception as e:
        logger.error(f"Ошибка is_agent_alive: {e}")
        return False