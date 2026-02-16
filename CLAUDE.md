# CLAUDE.md - Контекстная информация для Claude Code

> Этот файл предоставляет контекст для эффективной работы Claude Code с проектом Miminet

---

## 🎯 О проекте

**Miminet** — эмулятор компьютерных сетей на базе Mininet для образовательных целей.

### Основная функциональность
- Визуальное создание сетевых топологий (drag & drop)
- Эмуляция сетей с использованием Mininet
- Сбор метрик и анимация передачи пакетов
- Анализ pcap файлов
- Система тестирования/квизов для обучения

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────┐
│                   User Interface                 │
│              (Flask + Jinja2 + JS)              │
└──────────────────┬──────────────────────────────┘
                   │ HTTP/WebSocket
┌──────────────────▼──────────────────────────────┐
│              Frontend (Flask App)                │
│  - API endpoints (routes)                        │
│  - Authentication (OAuth: Google, VK, Yandex)    │
│  - Session management                            │
│  - Network configuration UI                      │
└──────────────────┬──────────────────────────────┘
                   │ RabbitMQ (async messaging)
┌──────────────────▼──────────────────────────────┐
│            Backend (Celery Worker)               │
│  - Mininet emulation                             │
│  - Network topology building                     │
│  - Metrics collection                            │
│  - Packet capture (pcap)                         │
└──────────────────────────────────────────────────┘

Supporting Services:
- PostgreSQL: User data, networks, simulations
- Redis: Caching, session storage
- RabbitMQ: Message broker
- Nginx: Load balancer, static files
```

### Ключевой workflow

1. **Создание сети**: User → Frontend UI → PostgreSQL
2. **Запуск симуляции**: Frontend → RabbitMQ → Celery Worker → Mininet
3. **Сбор результатов**: Mininet → Worker → RabbitMQ → Frontend → User

---

## 📂 Структура проекта

```
miminet/
├── front/                      # Frontend приложение
│   ├── src/
│   │   ├── app.py             # ГЛАВНЫЙ ФАЙЛ: Flask application entry point
│   │   ├── miminet_auth.py    # Аутентификация (OAuth, local)
│   │   ├── miminet_network.py # Управление сетями (CRUD)
│   │   ├── miminet_simulation.py # Запуск симуляций
│   │   ├── miminet_model.py   # SQLAlchemy модели (User, Network)
│   │   ├── miminet_host.py    # Конфигурация устройств
│   │   ├── miminet_shark.py   # Анализ pcap файлов
│   │   ├── tasks.py           # Celery задачи (frontend)
│   │   ├── quiz/              # Система квизов
│   │   ├── static/            # CSS, JS, images
│   │   └── templates/         # Jinja2 шаблоны
│   ├── tests/                 # Frontend тесты (Selenium)
│   ├── requirements.txt
│   └── docker-compose.yml
│
├── back/                       # Backend worker
│   ├── src/
│   │   ├── tasks.py           # ГЛАВНЫЙ ФАЙЛ: Celery worker entry point
│   │   ├── emulator.py        # ЯДРО: Mininet emulation logic
│   │   ├── network.py         # Network topology classes
│   │   ├── network_schema.py  # Data validation schemas
│   │   ├── network_topology.py # Topology builders
│   │   ├── pkt_parser.py      # Packet parsing utilities
│   │   ├── jobs.py            # Job management (commands)
│   │   └── net_utils/         # Network utilities
│   ├── tests/                 # Backend тесты (pytest)
│   │   └── test_json/         # Test configurations
│   ├── requirements.txt
│   └── docker-compose.yml
│
├── ansible/                    # Deployment automation
├── rabbitmq/                   # RabbitMQ configuration
├── README.md                   # Project documentation
├── AGENTS.md                   # Architecture documentation (30KB)
└── start_all_containers.sh    # Quick start script
```

---

## 🔑 Ключевые файлы и их назначение

### Frontend

| Файл | Назначение | Важность |
|------|-----------|----------|
| `front/src/app.py` | Точка входа Flask, регистрация роутов, инициализация | 🔴 Критический |
| `front/src/miminet_network.py` | CRUD операции с сетями, конфигурация | 🔴 Критический |
| `front/src/miminet_simulation.py` | Запуск/остановка симуляций | 🔴 Критический |
| `front/src/miminet_model.py` | SQLAlchemy модели (Database schema) | 🔴 Критический |
| `front/src/miminet_auth.py` | Аутентификация: OAuth + local | 🟡 Важный |
| `front/src/tasks.py` | Celery задачи на frontend | 🟡 Важный |
| `front/src/miminet_host.py` | Конфигурация устройств (host, switch, router) | 🟡 Важный |

### Backend

| Файл | Назначение | Важность |
|------|-----------|----------|
| `back/src/tasks.py` | Celery worker entry point | 🔴 Критический |
| `back/src/emulator.py` | ЯДРО эмуляции Mininet | 🔴 Критический |
| `back/src/network.py` | Network topology classes | 🔴 Критический |
| `back/src/network_schema.py` | Marshmallow schemas для валидации | 🟡 Важный |
| `back/src/jobs.py` | Job management (ping, traceroute, etc.) | 🟡 Важный |

---

## 💡 Ключевые концепции и термины

### Network (Сеть)
SQLAlchemy модель, представляющая сетевую топологию:
- `nodes`: список устройств (hosts, switches, routers, hubs)
- `edges`: связи между устройствами
- `config`: параметры (bandwidth, delay, loss)
- `guid`: уникальный идентификатор

### Simulation (Симуляция)
Процесс эмуляции сети в Mininet:
1. Построение топологии из JSON конфигурации
2. Запуск Mininet
3. Выполнение команд (ping, iperf, etc.)
4. Сбор метрик и pcap файлов
5. Возврат анимации пакетов

### Animation (Анимация)
JSON структура с информацией о передаче пакетов:
```json
[
  {
    "source": "h1",
    "target": "h2",
    "packet": {...},
    "timestamp": 123.456
  }
]
```

### Job (Задача)
Команда, выполняемая на устройстве:
- `ping`: ICMP ping
- `traceroute`: трассировка маршрута
- `iperf`: тестирование пропускной способности
- `custom`: произвольная bash команда

---

## 🔧 Технологический стек

### Frontend
- **Python 3.7+**
- **Flask 3.1.2**: Web framework
- **SQLAlchemy 2.0**: ORM для PostgreSQL
- **Flask-Login**: Управление сессиями
- **Flask-Migrate (Alembic)**: Database migrations
- **Celery 5.5**: Async task queue
- **Jinja2**: Template engine
- **Selenium**: E2E тестирование

### Backend
- **Python 3.7+**
- **Mininet 2.3+**: Network emulator (requires Linux + root)
- **ipmininet**: Enhanced Mininet (from GitHub fork)
- **Celery 5.5**: Task queue worker
- **dpkt**: Packet parsing
- **marshmallow**: Data validation

### Infrastructure
- **PostgreSQL 15**: Primary database
- **Redis 7**: Cache + session storage
- **RabbitMQ 3**: Message broker
- **Nginx**: Reverse proxy + load balancer
- **Docker + Docker Compose**: Containerization

---

## 🚀 Как запустить проект

### Быстрый старт (Docker)
```bash
# 1. Клонировать репозиторий
git clone git@github.com:mimi-net/miminet.git
cd miminet

# 2. Настроить файлы конфигурации
# Скопировать vk_auth.json в front/src/
# Создать miminet_secret.conf в front/src/ (случайная строка)

# 3. Запустить все контейнеры
./start_all_containers.sh

# 4. Открыть в браузере
http://localhost
```

### Миграции БД (если изменилась модель)
```bash
docker exec -it miminet bash
flask db migrate -m "Description of changes"
flask db upgrade
```

### Запуск тестов

**Frontend (Selenium):**
```bash
cd front/tests
sh docker/run.sh  # Запуск контейнеров с браузерами
pytest front/tests
```

**Backend (pytest):**
```bash
cd back/tests
sudo bash  # Mininet требует root
source .venv/bin/activate
export PYTHONPATH=$PYTHONPATH:../src
pytest .
```

---

## 🎨 Паттерны кода

### 1. Flask Route Pattern

```python
@app.route('/api/endpoint', methods=['POST'])
@login_required  # Если требуется аутентификация
def endpoint_name():
    """Краткое описание endpoint.
    
    Returns:
        JSON response with status code
    """
    data = request.get_json()
    
    # Валидация
    if not data or 'required_field' not in data:
        return jsonify({'error': 'Invalid input'}), 400
    
    # Бизнес-логика
    result = do_something(data, current_user)
    
    return jsonify(result), 200
```

### 2. SQLAlchemy Model Pattern

```python
class ModelName(db.Model):
    """Описание модели."""
    
    __tablename__ = 'table_name'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User', backref='items')
    
    def to_dict(self):
        """Сериализация в dict для JSON."""
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }
```

### 3. Celery Task Pattern

```python
from celery_app import app

@app.task(bind=True, max_retries=3)
def task_name(self, param1, param2):
    """Описание Celery задачи.
    
    Args:
        param1: Описание
        param2: Описание
    
    Returns:
        Result data
    """
    try:
        # Логика задачи
        result = do_work(param1, param2)
        return result
        
    except Exception as exc:
        # Retry с задержкой
        raise self.retry(exc=exc, countdown=60)
```

### 4. Mininet Emulation Pattern

```python
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch

def emulate(network_json):
    """Эмуляция сети в Mininet.
    
    Args:
        network_json: Network schema (marshmallow validated)
    
    Returns:
        tuple: (animation_json, pcap_files)
    """
    net = Mininet()
    
    # 1. Создание устройств
    hosts = {}
    for node in network_json.nodes:
        if node.type == 'host':
            hosts[node.name] = net.addHost(node.name, ip=node.ip)
    
    # 2. Создание связей
    for edge in network_json.edges:
        net.addLink(
            hosts[edge.source], 
            hosts[edge.target],
            bw=edge.bandwidth,
            delay=f'{edge.delay}ms',
            loss=edge.loss
        )
    
    # 3. Запуск сети
    net.start()
    
    # 4. Выполнение команд и сбор метрик
    animation = collect_animation(net, network_json.jobs)
    pcaps = collect_pcaps(net)
    
    # 5. Остановка
    net.stop()
    
    return animation, pcaps
```

---

## 📋 Частые задачи

### Добавить новый API endpoint

1. **Создать функцию-обработчик** в соответствующем файле (`miminet_*.py`)
2. **Зарегистрировать роут** в `app.py`:
   ```python
   app.add_url_rule('/api/new_endpoint', methods=['POST'], view_func=new_endpoint)
   ```
3. **Добавить тесты** в `front/tests/`

### Добавить новое поле в модель Network

1. **Обновить модель** в `miminet_model.py`:
   ```python
   class Network(db.Model):
       new_field = db.Column(db.String(100))
   ```
2. **Создать миграцию**:
   ```bash
   flask db migrate -m "Add new_field to Network"
   flask db upgrade
   ```
3. **Обновить метод `to_dict()`** если нужно

### Добавить новый тип устройства

1. **Обновить схему** в `back/src/network_schema.py`
2. **Добавить логику** в `back/src/emulator.py`:
   - Создание устройства
   - Конфигурация параметров
3. **Обновить UI** в `front/src/static/` и `templates/`

### Изменить параметры эмуляции

Файл: `back/src/emulator.py`, функция `emulate()`

Доступные параметры:
- `bandwidth`: Пропускная способность (Mbps)
- `delay`: Задержка (ms)
- `loss`: Потеря пакетов (%)
- `jitter`: Джиттер (ms)

---

## 🐛 Известные проблемы и их решения

### Mininet иногда падает с ошибкой

**Проблема**: Mininet может некорректно работать из-за race conditions  
**Решение**: В `back/src/tasks.py` реализован retry механизм (4 попытки)

```python
for _ in range(4):
    try:
        animation, pcaps = emulate(network_json)
        return json.dumps(animation), pcaps
    except Exception as e:
        error(e)
        continue
```

### WSL не поддерживается для backend

**Проблема**: Mininet требует нативный Linux kernel  
**Решение**: Используйте:
- Docker на Linux хосте
- Vagrant с VirtualBox/VMware
- Нативный Linux

### База данных не мигрирует

**Проблема**: Старая миграция или неправильный `MODE`  
**Решение**:
```bash
# Проверить MODE в .env
MODE=dev

# Пересоздать миграции
docker exec -it miminet bash
rm -rf migrations/
flask db init
flask db migrate
flask db upgrade
```

---

## 🧪 Тестирование

### Frontend тесты (Selenium)

**Структура:**
```
front/tests/
├── conftest.py          # Pytest fixtures
├── utils/
│   ├── locators.py      # Веб-элементы (XPATH, CSS)
│   ├── networks.py      # Классы для создания тестовых сетей
│   └── checkers.py      # Проверка корректности эмуляции
└── test_*.py            # Тестовые сценарии
```

**Пример теста:**
```python
def test_create_simple_network(driver, login):
    """Создание простой сети с двумя хостами."""
    # Использование классов из utils/networks.py
    network = TwoHostsNetwork(driver)
    network.create()
    network.run_simulation()
    
    # Проверка результата
    assert network.check_connectivity()
```

### Backend тесты (pytest)

**Структура:**
```
back/tests/
├── test_json/           # JSON конфигурации для тестов
│   ├── simple.json
│   └── complex.json
└── test_*.py            # Unit тесты
```

**Пример теста:**
```python
def test_emulation_two_hosts():
    """Эмуляция сети с двумя хостами."""
    with open('test_json/simple.json') as f:
        network_json = json.load(f)
    
    animation, pcaps = run_miminet(json.dumps(network_json))
    
    assert animation != "[]"
    assert len(pcaps) > 0
```

---

## 🔐 Безопасность

### Аутентификация

Поддерживаемые методы:
1. **Google OAuth** (`miminet_auth.py::google_login`)
2. **VK OAuth** (`miminet_auth.py::vk_login`)
3. **Yandex OAuth** (`miminet_auth.py::yandex_login`)
4. **Telegram OAuth** (`miminet_auth.py::tg_callback`)
5. **Local** (username/password, только dev mode)

### Требования к паролям

- Минимум 8 символов
- Хешируются через Werkzeug's `generate_password_hash`

### Изоляция

- Каждый пользователь видит только свои сети
- Фильтрация по `author_id` в запросах
- Shared networks: флаг `is_shared=True`

---

## 📊 База данных (PostgreSQL)

### Основные таблицы

```sql
-- Пользователи
users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    auth_provider VARCHAR(50),  -- 'google', 'vk', 'yandex', 'telegram', 'local'
    external_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
)

-- Сети
networks (
    id SERIAL PRIMARY KEY,
    guid UUID UNIQUE,
    author_id INTEGER REFERENCES users(id),
    name VARCHAR(100),
    nodes JSONB,               -- JSON массив устройств
    edges JSONB,               -- JSON массив связей
    config JSONB,              -- Параметры (bandwidth, delay, loss)
    animation JSONB,           -- Результаты последней симуляции
    is_shared BOOLEAN DEFAULT FALSE,
    is_task BOOLEAN DEFAULT FALSE,  -- Задание для quiz
    created_at TIMESTAMP DEFAULT NOW()
)

-- Quiz таблицы (упрощенно)
tests, sections, questions, answers, session_questions
```

### Важные индексы

```sql
CREATE INDEX idx_networks_author ON networks(author_id);
CREATE INDEX idx_networks_guid ON networks(guid);
CREATE INDEX idx_networks_shared ON networks(is_shared);
```

---

## 🌐 API Reference (основные endpoints)

### Networks

```
POST   /create_network              Создание новой сети
GET    /web_network?guid={guid}     Получение сети по GUID
POST   /delete_network               Удаление сети
POST   /network/copy_network         Копирование сети
POST   /post_network_nodes           Добавление устройств
POST   /post_nodes_edges             Добавление связей
POST   /move_network_nodes           Перемещение устройств
POST   /network/update_network_config Обновление конфигурации
```

### Simulation

```
POST   /run_simulation              Запуск эмуляции
GET    /check_simulation?guid={guid} Проверка статуса
```

### Host Configuration

```
POST   /host/save_config            Конфигурация host
POST   /host/router_save_config     Конфигурация router
POST   /host/switch_save_config     Конфигурация switch
POST   /edge/save_config            Конфигурация связи
POST   /host/delete_job             Удаление команды
```

### Authentication

```
GET    /auth/login.html             Страница входа
GET    /auth/google_login           Google OAuth redirect
GET    /auth/vk_login               VK OAuth redirect
GET    /auth/logout                 Выход
GET    /user/profile.html           Профиль пользователя
```

---

## 💬 Соглашения о коде

### Именование

- **Файлы**: `snake_case.py`
- **Функции**: `snake_case()`
- **Классы**: `PascalCase`
- **Константы**: `UPPER_SNAKE_CASE`
- **Переменные**: `snake_case`

### Docstrings

Используйте Google Style:

```python
def function_name(param1: str, param2: int) -> dict:
    """Краткое описание функции в одну строку.
    
    Более подробное описание, если нужно.
    Может быть несколько параграфов.
    
    Args:
        param1: Описание первого параметра
        param2: Описание второго параметра
    
    Returns:
        Описание возвращаемого значения
        
    Raises:
        ValueError: Когда возникает
        RuntimeError: Когда возникает
    
    Example:
        >>> function_name("test", 42)
        {'result': 'success'}
    """
    pass
```

### Imports

Порядок импортов:

```python
# 1. Стандартная библиотека
import os
import sys
from datetime import datetime

# 2. Сторонние библиотеки
from flask import Flask, request
from sqlalchemy import Column, Integer

# 3. Локальные импорты
from miminet_model import Network, User
from miminet_util import format_date
```

---

## 🔍 Debugging Tips

### Логи

**Frontend:**
```bash
docker logs -f miminet  # Flask logs
```

**Backend:**
```bash
docker logs -f celery   # Celery worker logs
```

**RabbitMQ:**
```bash
# Management UI: http://localhost:15672
# Username: guest, Password: guest
```

### Breakpoints

**Flask:**
```python
import pdb; pdb.set_trace()  # Python debugger
```

**Mininet:**
```python
from mininet.log import setLogLevel
setLogLevel('debug')  # Verbose mininet logs
```

### Проверка очереди RabbitMQ

```bash
docker exec -it rabbitmq rabbitmqctl list_queues
```

---

## 📚 Дополнительные ресурсы

### Документация проекта
- `README.md`: Основная документация
- `AGENTS.md`: Детальная архитектура (30KB, 1100 строк)
- `INDEX.md`: Навигация по документации
- `AGENTS_SUMMARY.md`: Краткое резюме архитектуры

### External Documentation
- [Mininet Documentation](http://mininet.org/walkthrough/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)

### Полезные команды

```bash
# Docker
docker ps                          # Список контейнеров
docker exec -it miminet bash       # Войти в контейнер
docker-compose logs -f             # Следить за логами

# Database
flask db migrate -m "message"      # Создать миграцию
flask db upgrade                   # Применить миграции
flask db downgrade                 # Откатить миграцию

# Tests
pytest front/tests -v              # Frontend тесты (verbose)
pytest back/tests -k test_name     # Запуск конкретного теста

# RabbitMQ
rabbitmqctl list_queues            # Список очередей
rabbitmqctl purge_queue queue_name # Очистить очередь
```

---

## ✅ Чек-лист для коммитов

Перед коммитом убедитесь:

- [ ] Код следует соглашениям проекта
- [ ] Добавлены/обновлены docstrings
- [ ] Добавлены тесты для новой функциональности
- [ ] Все тесты проходят (`pytest`)
- [ ] База данных мигрирует корректно
- [ ] Нет TODO/FIXME в коммите (если только это не intentional)
- [ ] Обновлена документация (если нужно)

---

## 🆘 Где искать помощь

### По функциональности

| Вопрос | Где искать |
|--------|-----------|
| Как создать сеть? | `front/src/miminet_network.py` |
| Как запустить симуляцию? | `front/src/miminet_simulation.py` + `back/src/emulator.py` |
| Как добавить устройство? | `front/src/miminet_host.py` |
| Как работает аутентификация? | `front/src/miminet_auth.py` |
| Как парсить пакеты? | `front/src/pcap_parser.py` + `back/src/pkt_parser.py` |
| Как работают тесты? | `front/tests/utils/networks.py` |

### По проблемам

| Проблема | Решение |
|----------|---------|
| Mininet не запускается | Проверить права (sudo), наличие Linux kernel |
| База данных недоступна | Проверить docker-compose, порты |
| RabbitMQ не работает | Проверить `docker logs rabbitmq` |
| Тесты падают | Проверить Selenium контейнеры, браузеры |

---

## 🎓 Обучающие материалы

### Для новых разработчиков

1. **День 1**: Прочитать `README.md` и `AGENTS_SUMMARY.md`
2. **День 2**: Запустить проект локально, создать тестовую сеть
3. **День 3**: Изучить `front/src/app.py` и `back/src/emulator.py`
4. **День 4**: Написать простой тест в `front/tests/`
5. **День 5**: Добавить новый API endpoint

### Для понимания архитектуры

Читать в следующем порядке:
1. `CLAUDE.md` (этот файл) — обзор
2. `AGENTS_SUMMARY.md` — краткая архитектура
3. `AGENTS.md` — детальная архитектура
4. Исходный код ключевых файлов

---

## 📞 Контакты и обратная связь

- **GitHub**: https://github.com/mimi-net/miminet
- **Website**: https://miminet.ru/
- **Issues**: https://github.com/mimi-net/miminet/issues

---

**Последнее обновление**: 16 февраля 2026  
**Версия**: 1.0  
**Статус**: ✅ Готов к использованию

---

*Этот файл создан для эффективной работы Claude Code с проектом Miminet. При внесении значительных изменений в архитектуру проекта, пожалуйста, обновите этот документ.*
