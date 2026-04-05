import { useState, useEffect } from 'react';
import axios from 'axios';
import { Plus, RefreshCw, Copy, Trash2 } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

interface Agent {
  id: number;
  name: string;
  token: string;
  status: string;
  last_seen: string | null;
}

interface Task {
  id: number;
  agent_id: number;
  type: string;
  status: string;
  created_at: string;
  result?: any;
  logs?: string;
}

export default function App() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTab, setSelectedTab] = useState(0);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  const [showCreateAgentModal, setShowCreateAgentModal] = useState(false);
  const [showCreateTaskModal, setShowCreateTaskModal] = useState(false);
  const [newAgentToken, setNewAgentToken] = useState('');

  const [selectedAgentForTask, setSelectedAgentForTask] = useState<number | null>(null);
  const [taskType, setTaskType] = useState('system_info');
  const [taskPayload, setTaskPayload] = useState<any>({});

  const fetchData = async () => {
    try {
      const [aRes, tRes] = await Promise.all([
        axios.get(`${API_BASE}/agents`),
        axios.get(`${API_BASE}/tasks`)
      ]);
      setAgents(aRes.data);
      setTasks(tRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 6000);
    return () => clearInterval(interval);
  }, []);

  // Создать агента
  const createAgent = async () => {
    try {
      const res = await axios.post(`${API_BASE}/agents/register`, {
        name: `agent-${Date.now().toString().slice(-4)}`
      });
      setNewAgentToken(res.data.token);
      setShowCreateAgentModal(true);
      fetchData();
    } catch (err) {
      alert("Не удалось создать агента");
    }
  };

  // Создать задачу
  const createTask = async () => {
    if (!selectedAgentForTask) return alert("Выберите агента!");
    try {
      await axios.post(`${API_BASE}/tasks`, {
        agent_id: selectedAgentForTask,
        type: taskType,
        payload: taskPayload
      });
      alert("✅ Задача создана!");
      setShowCreateTaskModal(false);
      setTaskPayload({});
      fetchData();
    } catch (err: any) {
      alert("Ошибка: " + (err.response?.data?.detail || err.message));
    }
  };
const copyToken = (token: string) => {
    navigator.clipboard.writeText(token);
    alert("Токен скопирован!");
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex">

      {/* SIDEBAR */}
      <div className="w-72 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-6 border-b border-gray-800 flex items-center gap-3">
          {/* ← Ваша картинка дедушки */}
          <img 
            src="/grandpa.png" 
            alt="Grandpa" 
            className="w-12 h-12 rounded-2xl object-contain border border-gray-700"
          />
          <div>
            <h1 className="text-3xl font-bold">Porksheyan</h1>
            <p className="text-cyan-400 text-sm">Agent System</p>
          </div>
        </div>

        <div className="flex-1 p-4 space-y-1">
          <button 
            onClick={() => setSelectedTab(0)} 
            className={`w-full text-left px-5 py-4 rounded-2xl text-lg ${selectedTab === 0 ? 'bg-gray-800 text-cyan-400' : 'hover:bg-gray-800'}`}
          >
            Дашборд
          </button>
          <button 
            onClick={() => setSelectedTab(1)} 
            className={`w-full text-left px-5 py-4 rounded-2xl text-lg ${selectedTab === 1 ? 'bg-gray-800 text-cyan-400' : 'hover:bg-gray-800'}`}
          >
            Агенты
          </button>
          <button 
            onClick={() => setSelectedTab(2)} 
            className={`w-full text-left px-5 py-4 rounded-2xl text-lg ${selectedTab === 2 ? 'bg-gray-800 text-cyan-400' : 'hover:bg-gray-800'}`}
          >
            Задачи
          </button>
        </div>

        <div className="p-6 border-t border-gray-800">
          <button
            onClick={createAgent}
            className="w-full bg-gray-800 hover:bg-gray-700 py-4 rounded-3xl flex items-center justify-center gap-3 font-medium"
          >
            <Plus className="w-5 h-5" /> Добавить агента
          </button>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="flex-1 p-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-semibold">
            {selectedTab === 0 && "Дашборд"}
            {selectedTab === 1 && "Агенты"}
            {selectedTab === 2 && "Задачи"}
          </h1>

          {selectedTab === 2 && (
            <div className="flex gap-4">
              <button onClick={fetchData} className="flex items-center gap-3 px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-3xl">
                <RefreshCw className="w-5 h-5" /> Обновить
              </button>
              <button
                onClick={() => setShowCreateTaskModal(true)}
                className="flex items-center gap-3 px-8 py-3 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold rounded-3xl"
              >
                <Plus className="w-6 h-6" /> Создать задачу
              </button>
            </div>
          )}
        </div>

        {/* Дашборд */}
        {selectedTab === 0 && (
          <div className="grid grid-cols-3 gap-6">
            <div className="bg-gray-900 rounded-3xl p-8">
              <p className="text-gray-400">Агентов онлайн</p>
              <p className="text-6xl font-bold text-emerald-400 mt-4">
                {agents.filter(a => a.status === 'online').length}
              </p>
            </div>
            <div className="bg-gray-900 rounded-3xl p-8">
              <p className="text-gray-400">Всего задач</p>
              <p className="text-6xl font-bold text-cyan-400 mt-4">{tasks.length}</p>
            </div>
            <div className="bg-gray-900 rounded-3xl p-8">
              <p className="text-gray-400">Выполнено</p>
              <p className="text-6xl font-bold text-emerald-400 mt-4">
                {tasks.filter(t => t.status === 'completed').length}
              </p>
            </div>
          </div>
        )}

        {/* Агенты */}
        {selectedTab === 1 && (
          <div className="bg-gray-900 rounded-3xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-sm">
                  <th className="text-left py-6 px-8">ID</th>
                  <th className="text-left py-6 px-8">Имя</th>
                  <th className="text-left py-6 px-8">Статус</th>
                  <th className="text-left py-6 px-8">Последний heartbeat</th>
                  <th className="text-right py-6 px-8">Действия</th>
                </tr>
              </thead>
              <tbody>
                {agents.map(agent => (
                  <tr key={agent.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="py-6 px-8 font-mono">#{agent.id}</td>
                    <td className="py-6 px-8 font-medium">{agent.name}</td>
                    <td className="py-6 px-8">
                      <span className={agent.status === 'online' ? 'text-emerald-400' : 'text-red-400'}>
                        ● {agent.status}
                      </span>
                    </td>
                    <td className="py-6 px-8 text-gray-400">
                      {agent.last_seen ? new Date(agent.last_seen).toLocaleString('ru-RU') : '—'}
                    </td>
                    <td className="py-6 px-8 text-right flex gap-4 justify-end">
                      <button onClick={() => copyToken(agent.token)} className="text-cyan-400 hover:text-white">Копировать токен</button>
                     
                    
                      
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Задачи */}
        {selectedTab === 2 && (
          <div className="bg-gray-900 rounded-3xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-sm">
                  <th className="text-left py-6 px-8">ID</th>
                  <th className="text-left py-6 px-8">Агент</th>
                  <th className="text-left py-6 px-8">Тип</th>
                  <th className="text-left py-6 px-8">Статус</th>
                  <th className="text-left py-6 px-8">Дата создания</th>
                  <th className="text-right py-6 px-8"></th>
                </tr>
              </thead>
              <tbody>
                {tasks.map(task => (
                  <tr 
                    key={task.id} 
                    className="border-b border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                    onClick={() => setSelectedTask(task)}
                  >
                    <td className="py-6 px-8 font-mono">#{task.id}</td>
                    <td className="py-6 px-8">#{task.agent_id}</td>
                    <td className="py-6 px-8">{task.type}</td>
                    <td className="py-6 px-8">
                      <span className={`px-4 py-1 rounded-full text-xs ${task.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' : task.status === 'running' ? 'bg-amber-500/20 text-amber-400' : 'bg-blue-500/20 text-blue-400'}`}>
                        {task.status}
                      </span>
                    </td>
                    <td className="py-6 px-8 text-gray-400 text-sm">
                      {new Date(task.created_at).toLocaleString('ru-RU')}
                    </td>
                    <td className="py-6 px-8 text-right text-cyan-400">Подробнее →</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Модальное окно просмотра результата задачи */}
      {selectedTask && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={() => setSelectedTask(null)}>
          <div className="bg-gray-900 w-full max-w-3xl mx-4 rounded-3xl p-8" onClick={e => e.stopPropagation()}>
            <h2 className="text-2xl font-bold mb-6">Задача #{selectedTask.id}</h2>
            
            <div className="grid grid-cols-2 gap-6 mb-8 text-sm">
              <div><strong>Тип:</strong> {selectedTask.type}</div>
              <div><strong>Агент:</strong> #{selectedTask.agent_id}</div>
              <div><strong>Статус:</strong> <span className={selectedTask.status === 'completed' ? 'text-emerald-400' : 'text-amber-400'}>{selectedTask.status}</span></div>
              <div><strong>Создано:</strong> {new Date(selectedTask.created_at).toLocaleString('ru-RU')}</div>
            </div>

            {selectedTask.result && (
              <div className="mb-8">
                <h3 className="font-semibold mb-3">Результат:</h3>
                <pre className="bg-gray-950 p-6 rounded-2xl overflow-auto max-h-96 text-sm">
                  {JSON.stringify(selectedTask.result, null, 2)}
                </pre>
              </div>
            )}

            {selectedTask.logs && (
              <div>
                <h3 className="font-semibold mb-3">Логи:</h3>
                <pre className="bg-gray-950 p-6 rounded-2xl overflow-auto max-h-80 text-emerald-300 whitespace-pre-wrap">
                  {selectedTask.logs}
                </pre>
              </div>
            )}

            <button 
              onClick={() => setSelectedTask(null)}
              className="mt-6 w-full py-4 bg-gray-800 hover:bg-gray-700 rounded-3xl"
            >
              Закрыть
            </button>
          </div>
        </div>
      )}

      {/* Модальное окно создания агента */}
      {showCreateAgentModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="bg-gray-900 rounded-3xl p-8 max-w-md w-full mx-4 text-center">
            <h3 className="text-2xl font-bold mb-4 text-emerald-400">Агент успешно создан!</h3>
            <p className="text-gray-400 mb-6">Скопируйте токен:</p>
            <div className="bg-gray-950 p-4 rounded-2xl font-mono break-all mb-6 text-cyan-300">
              {newAgentToken}
            </div>
            <button
              onClick={() => {
                navigator.clipboard.writeText(newAgentToken);
                alert("Токен скопирован!");
                setShowCreateAgentModal(false);
              }}
              className="w-full py-4 bg-cyan-500 text-black font-bold rounded-3xl"
            >
              Скопировать токен
            </button>
          </div>
        </div>
      )}

      {/* Модальное окно создания задачи */}
      {showCreateTaskModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="bg-gray-900 w-full max-w-lg mx-4 rounded-3xl p-8">
            <h2 className="text-2xl font-bold mb-6">Создать новую задачу</h2>

            <div className="space-y-6">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Агент</label>
                <select
                  className="w-full bg-gray-800 border border-gray-700 rounded-2xl p-4"
                  value={selectedAgentForTask || ''}
                  onChange={(e) => setSelectedAgentForTask(Number(e.target.value))}
                >
                  <option value="">— Выберите агента —</option>
                  {agents.map(a => (
                    <option key={a.id} value={a.id}>{a.name} (#{a.id})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Тип задачи</label>
                <select
                  className="w-full bg-gray-800 border border-gray-700 rounded-2xl p-4"
                  value={taskType}
                  onChange={(e) => {
                    setTaskType(e.target.value);
                    setTaskPayload({});
                  }}
                >
                  <option value="system_info">Полная информация о системе</option>
                  <option value="host_info">Hostname, IP, ОС</option>
                  <option value="network_info">Сетевые интерфейсы</option>
                  <option value="check_port">Проверка порта</option>
                  <option value="run_command">Выполнить команду</option>
                </select>
              </div>

              {taskType === 'check_port' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-gray-400">Хост</label>
                    <input 
                      type="text" 
                      className="w-full bg-gray-800 border border-gray-700 rounded-2xl p-4 mt-1" 
                      value={taskPayload.host || '127.0.0.1'} 
                      onChange={e => setTaskPayload({...taskPayload, host: e.target.value})} 
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-400">Порт</label>
                    <input 
                      type="number" 
                      className="w-full bg-gray-800 border border-gray-700 rounded-2xl p-4 mt-1" 
                      value={taskPayload.port || 80} 
                      onChange={e => setTaskPayload({...taskPayload, port: Number(e.target.value)})} 
                    />
                  </div>
                </div>
              )}

              {taskType === 'run_command' && (
                <div>
                  <label className="text-sm text-gray-400">Команда</label>
                  <input 
                    type="text" 
                    className="w-full bg-gray-800 border border-gray-700 rounded-2xl p-4 mt-1" 
                    value={taskPayload.command || ''} 
                    onChange={e => setTaskPayload({...taskPayload, command: e.target.value})} 
                  />
                </div>
              )}
            </div>

            <div className="flex gap-4 mt-10">
              <button onClick={() => setShowCreateTaskModal(false)} className="flex-1 py-5 border border-gray-700 rounded-3xl hover:bg-gray-800">Отмена</button>
              <button onClick={createTask} className="flex-1 py-5 bg-cyan-500 text-black font-bold rounded-3xl">Создать задачу</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}