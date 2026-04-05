from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Dict, Any
import secrets
from datetime import datetime, timedelta
import logging

from app.database import SessionLocal, engine
import app.database as models
from app.redis_client import push_task
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Agent_Porksheyan")
# Папка, куда будет скопирована сборка фронтенда (см. Dockerfile)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

@app.get("/grandpa.png")
async def grandpa():
    return FileResponse("static/grandpa.png")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



# AGENTS


@app.post("/agents/register")
def register_agent(data: Dict[str, Any], db: Session = Depends(get_db)):
    name = data.get("name", "unknown")
    # Проверка существующего агента
    existing_agent = db.query(models.Agent).filter(models.Agent.name == name).first()
    if existing_agent:
        existing_agent.token = secrets.token_urlsafe(32)
        existing_agent.status = "online"
        existing_agent.last_seen = datetime.utcnow()
        db.commit()
        db.refresh(existing_agent)
        logger.info(f"Агент {name} перерегистрирован (ID: {existing_agent.id})")
        return {"agent_id": existing_agent.id, "token": existing_agent.token}
    token = secrets.token_urlsafe(32)
    agent = models.Agent(name=name, token=token, status="online", last_seen=datetime.utcnow())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    logger.info(f"Новый агент зарегистрирован: {agent.name} (ID: {agent.id})")
    return {"agent_id": agent.id, "token": token}


@app.post("/agents/heartbeat")
def heartbeat(data: Dict[str, Any], x_agent_token: str = Header(...), db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.token == x_agent_token).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Invalid token")
    agent.last_seen = datetime.utcnow()
    agent.status = "online"
    db.commit()
    return {"ok": True}


@app.get("/agents")
def list_agents(db: Session = Depends(get_db)):
    return db.query(models.Agent).all()

# TASKS

@app.post("/tasks")
def create_task(task: Dict[str, Any], db: Session = Depends(get_db)):
    db_task = models.Task(
        agent_id=task.get("agent_id"),
        type=task.get("type"),
        payload=task.get("payload", {}),
        status="pending"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    logger.info(f"Задача #{db_task.id} ({db_task.type}) создана для агента #{db_task.agent_id}")
    # Redis (если не работает – только предупреждение)
    try:
        push_task(db_task.agent_id, db_task.id, db_task.type, db_task.payload)
    except Exception as e:
        logger.warning(f"Redis push failed: {e}")
    return db_task


@app.get("/agents/tasks/next")
def get_next_task(x_agent_token: str = Header(...), db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.token == x_agent_token).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Invalid token")
    task = db.query(models.Task).filter(
        models.Task.agent_id == agent.id,
        models.Task.status == "pending"
    ).order_by(models.Task.created_at.asc()).first()
    if not task:
        return {}
    task.status = "running"
    task.started_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    logger.info(f"→ Задача #{task.id} ({task.type}) отдана агенту #{agent.id}")
    return {"id": task.id, "type": task.type, "payload": task.payload}


@app.patch("/tasks/{task_id}")
def update_task_status(task_id: int, data: Dict[str, Any], x_agent_token: str = Header(...), db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.token == x_agent_token).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Invalid token")
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.agent_id != agent.id:
        raise HTTPException(status_code=403, detail="Task not assigned to this agent")
    task.status = data.get("status", task.status)
    db.commit()
    logger.info(f"Статус задачи #{task_id} обновлён на '{task.status}' агентом #{agent.id}")
    return {"ok": True}


@app.post("/tasks/{task_id}/result")
def submit_result(task_id: int, result: Dict[str, Any], x_agent_token: str = Header(...), db: Session = Depends(get_db)):
    try:
        agent = db.query(models.Agent).filter(models.Agent.token == x_agent_token).first()
        if not agent:
            logger.error(f"Invalid token при отправке результата задачи #{task_id}")
            raise HTTPException(status_code=403, detail="Invalid token")
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if not task:
            logger.error(f"Задача #{task_id} не найдена")
            raise HTTPException(status_code=404, detail="Task not found")
        if task.agent_id != agent.id:
            logger.error(f"Агент #{agent.id} пытается отправить результат для чужой задачи #{task_id} (агент #{task.agent_id})")
            raise HTTPException(status_code=403, detail="Task not assigned to this agent")
        task.status = result.get("status", "completed")
        task.result = result.get("result")
        task.logs = result.get("logs")
        task.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        logger.info(f"Результат задачи #{task_id} сохранён. Статус: {task.status}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при сохранении результата задачи #{task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    return db.query(models.Task).all()


@app.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/reset-stale")
def reset_stale_tasks(minutes: int = 10, db: Session = Depends(get_db)):
    stale_time = datetime.utcnow() - timedelta(minutes=minutes)
    stale_tasks = db.query(models.Task).filter(
        models.Task.status == "running",
        models.Task.started_at < stale_time
    ).all()
    count = 0
    for task in stale_tasks:
        task.status = "pending"
        task.started_at = None
        count += 1
        logger.warning(f"Сброшена зависшая задача #{task.id}")
    db.commit()
    return {"reset_count": count}