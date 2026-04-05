# Agent Porksheyan

> Система распределённого мониторинга и выполнения задач с использованием агентов, FastAPI и опциональной очереди Redis.

---

## 📋 Описание

**Agent Porksheyan** — это распределённая система, где центральный сервер управляет агентами, распределяет задачи и собирает результаты.

Агенты:
- периодически опрашивают сервер (**HTTP polling**)
- получают задачи
- выполняют их
- отправляют результат обратно

> ⚠️ Redis используется **опционально** и только для уведомлений — система полностью работает без него.

---

## 🏗️ Архитектура

```
Agent → FastAPI → Database
           ↓
         Redis (опционально)
```

| Компонент | Описание |
|----------|--------|
| FastAPI сервер | FastAPI и логика управления |
| БД (SQLite/PostgreSQL) | Хранение состояния |
| Redis (опционально) | Уведомления о задачах |
| Agent (Python) | Исполнитель задач |

> ❗ Агент получает задачи через `/agents/tasks/next`, а не из Redis.

---

## ⚙️ Функциональность

### 🤖 Агенты
- Регистрация и получение токена
- Аутентификация по токену
- Автоперерегистрация при ошибке
- Heartbeat (по умолчанию 1 сек)
- До **4 задач параллельно**

### 📦 Задачи
- Создание через API (`POST /tasks`)
- Статусы:
  - `pending`
  - `running`
  - `completed`
  - `failed`
- Получение агентом через polling

### ⚡ Выполнение
- Выполнение в потоках
- Повтор отправки результата (до 3 раз)
- Сохранение результата в БД (JSON)

### ➕ Дополнительно
- Сброс зависших задач
- Batch-задачи
- Проверка systemd сервисов (Linux)

---

## 🛠️ Технологии

- FastAPI
- SQLAlchemy
- Redis (опционально)
- SQLite / PostgreSQL
- Docker
- python-dotenv
- tenacity
- psutil
- colorama

---

## 🗄️ База данных

### Agents

| Поле | Описание |
|------|--------|
| id | ID |
| name | Имя |
| token | Токен |
| status | online/offline |
| last_seen | Последний heartbeat |

### Tasks

| Поле | Описание |
|------|--------|
| id | ID |
| agent_id | Агент |
| type | Тип |
| payload | JSON |
| status | Статус |
| result | JSON |
| logs | Логи |

> 💡 Вся логика состояния хранится в БД.

---

## 🔄 Принцип работы

1. Агент регистрируется  
2. Получает токен  
3. Сервер создаёт задачи  
4. Агент опрашивает `/agents/tasks/next`  
5. Выполняет задачу  
6. Отправляет результат  
7. Сервер сохраняет результат  

---

## 📁 Структура проекта

```
Agent_Porksheyan/
├── agent/
│   ├── agent.py
│   ├── config.py
│   ├── checks/
│   └── .env
├── app/
│   ├── database.py
│   ├── redis_client.py
├── front/
├── Dockerfile
├── docker-compose.yml
├── main.py
├── requirements.txt
└── README.md
```

---

## 🚀 Установка и запуск

### 1. Клонирование

```bash
git clone <https://github.com/Def0ltT3pe/Agent_Porksheyan_2.0>
cd project
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

---

### 3. Настройка `.env` (agent)

```ini
AGENT_NAME=my-agent-1
API_URL=http://127.0.0.1:8000
DEBUG_MODE=True
HEARTBEAT_INTERVAL=1
TASK_POLL_INTERVAL=0.5
MAX_CONCURRENT_TASKS=4
```

---

### 4. Redis (опционально)

```bash
redis-server
```

---

### 5. Запуск сервера

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://127.0.0.1:8000  
- Docs: http://127.0.0.1:8000/docs  

---

### 6. Запуск агента

```bash
cd agent
python agent.py
```

---

## 📡 API

### Регистрация агента

```http
POST /agents/register
```

```json
{
  "name": "my-agent",
  "hostname": "server01"
}
```

---

### Создание задачи

```http
POST /tasks
```

```json
{
  "agent_id": 1,
  "type": "system_info",
  "payload": {}
}
```

---

### Получение задач

```http
GET /tasks
GET /tasks/{id}
```

---

### Сброс зависших задач

```http
POST /tasks/reset-stale?minutes=10
```

---

## 🐳 Docker

```bash
docker-compose up --build
```

> ⚠️ Для доступа к системе хоста агенту могут понадобиться дополнительные права.

---

## 🔒 Безопасность

- Токены (`X-Agent-Token`)
- Проверка принадлежности задач агенту
- Белый список команд
- Запрет опасных команд (`rm`, `sudo`, и др.)

---

## 🔮 Планы развития

- WebSocket вместо polling  
- Веб-интерфейс  
- Cron-задачи  
- Масштабирование  
- PostgreSQL для production  
- Метрики и алертинг  

---

## 📌 Итог

Проект реализует:
- отказоустойчивую систему  
- распределённое выполнение задач  
- независимость от Redis  
- автоматическое восстановление после сбоев  

--- 

## 👥 Команда

|------|--------|
Ичёткин Никита | https://t.me/@NokJoy
Лысота Дмитрий | https://t.me/@SVarG02
Махно Елизавета | https://t.me/@Liza_M520
Колесников Ярослав | https://t.me/@OmegaPivo
Султанов Руслан | https://t.me/@Syl_Rus
