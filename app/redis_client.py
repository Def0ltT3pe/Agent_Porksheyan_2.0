import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

def push_task(agent_id: int, task_id: int, task_type: str, payload: dict) -> None:
    """Поместить задачу в очередь конкретного агента"""
    queue_name = f"tasks:{agent_id}"
    task = {
        "id": task_id,
        "type": task_type,
        "payload": payload
    }
    redis_client.lpush(queue_name, json.dumps(task))

def pop_task(agent_id: int, timeout: int = 2) -> dict | None:
    """Агент забирает задачу из своей очереди"""
    queue_name = f"tasks:{agent_id}"
    result = redis_client.brpop(queue_name, timeout=timeout)
    if result:
        _, task_json = result
        return json.loads(task_json)
    return None

def set_agent_heartbeat(agent_id: int, ttl: int = 30) -> None:
    """Агент сообщает, что жив (храним в Redis)"""
    redis_client.set(f"agent:{agent_id}:heartbeat", "1", ex=ttl)

def is_agent_alive(agent_id: int) -> bool:
    """Проверить, жив ли агент по Redis"""
    return redis_client.exists(f"agent:{agent_id}:heartbeat") == 1