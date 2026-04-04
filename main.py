from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Dict, Any
import secrets
from datetime import datetime

from app.database import SessionLocal, engine
import app.database as models
from app.redis_client import push_task, pop_task


# Создаём таблицы
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Agent_Porksheyan")


# --- DB dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# 🔹 AGENTS
# =========================

@app.post("/agents/register")
def register_agent(data: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Агент регистрируется.
    Принимаем ЛЮБЫЕ поля (как у тебя в агенте)
    """
    token = secrets.token_urlsafe(32)

    agent = models.Agent(
        name=data.get("name", "unknown"),
        token=token,
        status="online",
        last_seen=datetime.utcnow()
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return {
        "agent_id": agent.id,
        "token": token
    }


@app.post("/agents/heartbeat")
def heartbeat(
    data: Dict[str, Any],
    x_agent_token: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Агент сообщает, что жив
    """
    agent = db.query(models.Agent).filter(
        models.Agent.token == x_agent_token
    ).first()

    if not agent:
        raise HTTPException(status_code=403, detail="Invalid token")

    agent.last_seen = datetime.utcnow()
    agent.status = "online"

    db.commit()

    return {"ok": True}


@app.get("/agents")
def list_agents(db: Session = Depends(get_db)):
    return db.query(models.Agent).all()


# =========================
# 🔹 TASKS
# =========================

@app.post("/tasks")
def create_task(task: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Создание задачи
    Пример:
    {
        "agent_id": 1,
        "type": "system_info",
        "payload": {}
    }
    """
    db_task = models.Task(
        agent_id=task.get("agent_id"),
        type=task.get("type"),
        payload=task.get("payload", {}),
        status="pending"
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    db.refresh(db_task)
    push_task(agent_id=db_task.agent_id, task_id=db_task.id, task_type=db_task.type, payload=db_task.payload)
    return db_task




@app.get("/agents/tasks/next")
def get_next_task(
    x_agent_token: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Агент получает следующую задачу
    """
    agent = db.query(models.Agent).filter(
        models.Agent.token == x_agent_token
    ).first()

    if not agent:
        raise HTTPException(status_code=403, detail="Invalid token")

    task = db.query(models.Task).filter(
        models.Task.agent_id == agent.id,
        models.Task.status == "pending"
    ).order_by(models.Task.created_at).first()

    if not task:
        return {}

    task.status = "running"
    task.started_at = datetime.utcnow()

    db.commit()

    return {
        "id": task.id,
        "type": task.type,
        "payload": task.payload
    }


@app.patch("/tasks/{task_id}")
def update_task_status(
    task_id: int,
    data: Dict[str, Any],
    x_agent_token: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Агент обновляет статус (running и т.д.)
    """
    agent = db.query(models.Agent).filter(
        models.Agent.token == x_agent_token
    ).first()

    if not agent:
        raise HTTPException(status_code=403)

    task = db.query(models.Task).filter(models.Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404)

    task.status = data.get("status", task.status)
    db.commit()

    return {"ok": True}


@app.post("/tasks/{task_id}/result")
def submit_result(
    task_id: int,
    result: Dict[str, Any],
    x_agent_token: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Агент отправляет результат
    """
    agent = db.query(models.Agent).filter(
        models.Agent.token == x_agent_token
    ).first()

    if not agent:
        raise HTTPException(status_code=403, detail="Invalid token")

    task_data = pop_task(agent.id)
    if not task_data:
        return {}

    task = db.query(models.Task).filter(models.Task.id == task_data["id"]).first()
    if task:
        task.status = "running"
        task.started_at = datetime.utcnow()
        db.commit()

    return task_data


@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    return db.query(models.Task).all()


@app.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404)
    return task