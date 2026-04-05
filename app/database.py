# database.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import datetime
from typing import Optional, Dict, Any, List
import os

# ========== НАСТРОЙКИ ==========
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATA_DIR}/task_system.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ========== МОДЕЛИ ==========
class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="offline")
    last_seen = Column(DateTime, nullable=True)
    description = Column(String, nullable=True)
    tags = Column(JSON, default=[])


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    agent_id = Column(Integer, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    payload = Column(JSON, default={})
    status = Column(String, default="pending", index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    result = Column(JSON, nullable=True)
    logs = Column(Text, nullable=True)

    priority = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)


# ========== DEPENDENCY ==========
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ... (функции create_agent, get_agent, create_task и т.д. остаются те же)
# Я не буду дублировать их для краткости, они у вас уже есть.


# ========== CRUD AGENTS ==========
def create_agent(db: Session, name: str, token: str, description: str = None, tags: List = None) -> Agent:
    """Создать нового агента"""
    agent = Agent(
        name=name,
        token=token,
        status="online",
        last_seen=datetime.utcnow(),
        description=description,
        tags=tags or []
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_agent(db: Session, **kwargs) -> Optional[Agent]:
    """Получить агента по любому полю"""
    return db.query(Agent).filter_by(**kwargs).first()


def get_all_agents(db: Session, skip: int = 0, limit: int = 100) -> List[Agent]:
    """Получить всех агентов (для фронтенда)"""
    return db.query(Agent).offset(skip).limit(limit).all()


def update_agent_status(db: Session, agent_id: int, status: str) -> None:
    """Обновить статус агента"""
    db.query(Agent).filter(Agent.id == agent_id).update({
        "status": status,
        "last_seen": datetime.utcnow()
    })
    db.commit()


def delete_agent(db: Session, agent_id: int) -> bool:
    """Удалить агента"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent:
        db.delete(agent)
        db.commit()
        return True
    return False


# ========== CRUD TASKS ==========
def create_task(db: Session, agent_id: int, task_type: str, payload: Dict = None, priority: int = 0) -> Task:
    """Создать новую задачу"""
    task = Task(
        agent_id=agent_id,
        type=task_type,
        payload=payload or {},
        status="pending",
        priority=priority
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Optional[Task]:
    """Получить задачу по ID"""
    return db.query(Task).filter(Task.id == task_id).first()


def get_next_task(db: Session, agent_id: int) -> Optional[Task]:
    """Получить следующую задачу для агента (с учётом приоритета)"""
    return db.query(Task).filter(
        Task.agent_id == agent_id,
        Task.status == "pending"
    ).order_by(Task.priority.desc(), Task.created_at).first()


def get_tasks_by_agent(db: Session, agent_id: int, limit: int = 100) -> List[Task]:
    """Получить все задачи агента (для фронтенда)"""
    return db.query(Task).filter(
        Task.agent_id == agent_id
    ).order_by(Task.created_at.desc()).limit(limit).all()


def get_all_tasks(db: Session, skip: int = 0, limit: int = 100) -> List[Task]:
    """Получить все задачи (для фронтенда)"""
    return db.query(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()


def update_task_status(db: Session, task_id: int, status: str) -> None:
    """Обновить статус задачи"""
    updates = {"status": status}

    if status == "running" and not db.query(Task).filter(Task.id == task_id).first().started_at:
        updates["started_at"] = datetime.utcnow()
    elif status in ["completed", "failed", "cancelled"]:
        updates["finished_at"] = datetime.utcnow()

    db.query(Task).filter(Task.id == task_id).update(updates)
    db.commit()


def complete_task(db: Session, task_id: int, result: Any, logs: str = None) -> None:
    """Завершить задачу успешно"""
    db.query(Task).filter(Task.id == task_id).update({
        "status": "completed",
        "result": str(result),
        "logs": logs,
        "finished_at": datetime.utcnow()
    })
    db.commit()


def fail_task(db: Session, task_id: int, error: str, logs: str = None) -> None:
    """Отметить задачу как проваленную"""
    # Увеличиваем счётчик ретраев
    task = db.query(Task).filter(Task.id == task_id).first()
    retry_count = (task.retry_count or 0) + 1

    # Если превышен лимит ретраев - окончательно проваливаем
    if retry_count >= (task.max_retries or 3):
        db.query(Task).filter(Task.id == task_id).update({
            "status": "failed",
            "result": error,
            "logs": logs,
            "finished_at": datetime.utcnow(),
            "retry_count": retry_count
        })
    else:
        # Иначе возвращаем в pending для повторной попытки
        db.query(Task).filter(Task.id == task_id).update({
            "status": "pending",
            "logs": logs,
            "retry_count": retry_count
        })

    db.commit()


def delete_old_tasks(db: Session, days: int = 30) -> int:
    """Удалить старые завершённые задачи"""
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(Task).filter(
        Task.status.in_(["completed", "failed"]),
        Task.finished_at < cutoff_date
    ).delete()

    db.commit()
    return deleted


# ========== СТАТИСТИКА (ДЛЯ ФРОНТЕНДА) ==========
def get_system_statistics(db: Session) -> Dict[str, Any]:
    """Получить общую статистику системы"""
    agents = db.query(Agent).all()
    tasks = db.query(Task).all()

    return {
        "agents": {
            "total": len(agents),
            "online": len([a for a in agents if a.status == "online"]),
            "offline": len([a for a in agents if a.status == "offline"]),
            "busy": len([a for a in agents if a.status == "busy"])
        },
        "tasks": {
            "total": len(tasks),
            "pending": len([t for t in tasks if t.status == "pending"]),
            "running": len([t for t in tasks if t.status == "running"]),
            "completed": len([t for t in tasks if t.status == "completed"]),
            "failed": len([t for t in tasks if t.status == "failed"])
        }
    }


def get_task_statistics_by_type(db: Session) -> Dict[str, Dict]:
    """Статистика по типам задач"""
    tasks = db.query(Task).all()
    stats = {}

    for task in tasks:
        if task.type not in stats:
            stats[task.type] = {"total": 0, "completed": 0, "failed": 0}

        stats[task.type]["total"] += 1
        if task.status == "completed":
            stats[task.type]["completed"] += 1
        elif task.status == "failed":
            stats[task.type]["failed"] += 1

    return stats


# ========== ИНИЦИАЛИЗАЦИЯ ==========
Base.metadata.create_all(bind=engine)
print(f"✅ База данных инициализирована: {DATABASE_URL}")
print(f"📊 Таблицы: agents, tasks")