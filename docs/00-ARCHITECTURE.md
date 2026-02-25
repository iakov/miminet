# 🏗️ Архитектура Miminet

## Обзор архитектуры

```text
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

```text
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
├── CLAUDE.md                   # Этот файл (навигация)
├── docs/                       # Документация
│   ├── 00-ARCHITECTURE.md      # Этот файл
│   ├── 01-GETTING_STARTED.md   # Запуск проекта
│   ├── 02-DEVELOPMENT.md       # Разработка
│   ├── 03-TESTING.md           # Тестирование
│   ├── 04-DATABASE_AND_API.md  # БД и API
│   └── 05-OPERATIONS.md        # Операции и отладка
└── start_all_containers.sh    # Quick start script
```

---

## 🔑 Ключевые файлы и их назначение

### Файлы Frontend

| Файл | Назначение | Важность |
| ------ | ----------- | ---------- |
| `front/src/app.py` | Точка входа Flask, регистрация роутов, инициализация | 🔴 Критический |
| `front/src/miminet_network.py` | CRUD операции с сетями, конфигурация | 🔴 Критический |
| `front/src/miminet_simulation.py` | Запуск/остановка симуляций | 🔴 Критический |
| `front/src/miminet_model.py` | SQLAlchemy модели (Database schema) | 🔴 Критический |
| `front/src/miminet_auth.py` | Аутентификация: OAuth + local | 🟡 Важный |
| `front/src/tasks.py` | Celery задачи на frontend | 🟡 Важный |
| `front/src/miminet_host.py` | Конфигурация устройств (host, switch, router) | 🟡 Важный |

### Файлы Backend

| Файл | Назначение | Важность |
| ------ | ----------- | ---------- |
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

### Технологии Frontend

- **Python 3.7+**
- **Flask 3.1.2**: Web framework
- **SQLAlchemy 2.0**: ORM для PostgreSQL
- **Flask-Login**: Управление сессиями
- **Flask-Migrate (Alembic)**: Database migrations
- **Celery 5.5**: Async task queue
- **Jinja2**: Template engine
- **Selenium**: E2E тестирование

### Технологии Backend

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
