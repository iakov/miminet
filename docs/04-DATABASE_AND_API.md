# 📊 База данных и API

## 🔐 Безопасность

### Аутентификация

Поддерживаемые методы в `front/src/miminet_auth.py`:

1. **Google OAuth** (`google_login()`)
2. **VK OAuth** (`vk_login()`)  
3. **Yandex OAuth** (`yandex_login()`)
4. **Telegram OAuth** (`tg_callback()`)
5. **Local** (username/password, только dev mode)

### Требования к паролям

- Минимум 8 символов
- Требуется хотя бы одна цифра
- Хешируются через `werkzeug.security.generate_password_hash`

### Изоляция данных

- Каждый пользователь видит только свои сети
- Все запросы фильтруются по `author_id` в WHERE clause
- Shared networks: флаг `is_shared=True` позволяет другим видеть сеть
- Admin-функции: проверка роли `current_user.is_admin`

---

## 💾 База данных (PostgreSQL 15)

### Главные таблицы

#### users

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    auth_provider VARCHAR(50),  -- 'google', 'vk', 'yandex', 'telegram', 'local'
    external_id VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (auth_provider, external_id)
);
```

#### networks

```sql
CREATE TABLE networks (
    id SERIAL PRIMARY KEY,
    guid UUID UNIQUE NOT NULL,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    nodes JSONB NOT NULL,               -- JSON массив \{type, id, name, ip, ...\}
    edges JSONB NOT NULL,               -- JSON массив \{source, target, bandwidth, ...\}
    config JSONB,                       -- Глобальные параметры сети
    animation JSONB,                    -- Результаты последней эмуляции
    pcap_files JSONB,                   -- Список pcap файлов из последней эмуляции
    is_shared BOOLEAN DEFAULT FALSE,
    is_task BOOLEAN DEFAULT FALSE,      -- Является ли задачей для quiz
    last_simulation_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### Quiz-таблицы (упрощенно)

```sql
CREATE TABLE tests (               -- Название: "Тест 1", "Тест 2"
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE sections (             -- Разделы внутри теста
    id SERIAL PRIMARY KEY,
    test_id INTEGER REFERENCES tests(id),
    name VARCHAR(100),
    order_num INTEGER
);

CREATE TABLE questions (            -- Вопросы
    id SERIAL PRIMARY KEY,
    section_id INTEGER REFERENCES sections(id),
    question_text TEXT,
    question_type VARCHAR(20),      -- 'single_choice', 'multiple_choice', 'text'
    order_num INTEGER
);

CREATE TABLE answers (              -- Варианты ответов
    id SERIAL PRIMARY KEY,
    question_id INTEGER REFERENCES questions(id),
    answer_text TEXT,
    is_correct BOOLEAN,
    order_num INTEGER
);

CREATE TABLE session_questions (    -- Данные о ответах пользователя
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    question_id INTEGER REFERENCES questions(id),
    given_answer TEXT,
    is_correct BOOLEAN,
    answers_at TIMESTAMP DEFAULT NOW()
);
```

### Индексы для оптимизации

```sql
CREATE INDEX idx_networks_author ON networks(author_id);
CREATE INDEX idx_networks_guid ON networks(guid);
CREATE INDEX idx_networks_shared ON networks(is_shared);
CREATE INDEX idx_networks_created_at ON networks(created_at DESC);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_auth ON users(auth_provider, external_id);

CREATE INDEX idx_session_questions_user ON session_questions(user_id);
CREATE INDEX idx_session_questions_question ON session_questions(question_id);
```

---

## 🌐 API Reference

### Endpoints для сетей

#### Создание сети

```http
POST /create_network HTTP/1.1
Content-Type: application/json

{
  "name": "My Network",
  "description": "Test network"
}
```

**Response:**

```json
{
  "id": 1,
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Network",
  "author_id": 1,
  "created_at": "2026-02-25T10:30:00"
}
```

#### Получение сети

```http
GET /web_network?guid=550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
```

**Response:**

```json
{
  "id": 1,
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Network",
  "nodes": [...],
  "edges": [...],
  "config": {...},
  "animation": [...],
  "created_at": "2026-02-25T10:30:00"
}
```

#### Удаление сети

```http
POST /delete_network HTTP/1.1
Content-Type: application/json

{ "guid": "550e8400-e29b-41d4-a716-446655440000" }
```

#### Копирование сети

```http
POST /network/copy_network HTTP/1.1
Content-Type: application/json

{ "guid": "550e8400-e29b-41d4-a716-446655440000" }
```

---

### Endpoints для устройств (nodes)

#### Добавление устройств

```http
POST /post_network_nodes HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "nodes": [
    {
      "id": "h1",
      "type": "host",
      "name": "Host 1",
      "ip": "10.0.0.1"
    },
    {
      "id": "s1",
      "type": "switch",
      "name": "Switch 1"
    }
  ]
}
```

#### Перемещение устройств

```http
POST /move_network_nodes HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "nodes": [
    { "id": "h1", "x": 100, "y": 150 }
  ]
}
```

---

### Endpoints для связей (edges)

#### Добавление связей

```http
POST /post_nodes_edges HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "edges": [
    {
      "source": "h1",
      "target": "s1",
      "bandwidth": 100,
      "delay": 10,
      "loss": 0.5
    }
  ]
}
```

#### Конфигурация связи

```http
POST /edge/save_config HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "source": "h1",
  "target": "s1",
  "bandwidth": 100,
  "delay": 5,
  "loss": 0
}
```

---

### Endpoints для конфигурации хостов

#### Конфигурация хоста

```http
POST /host/save_config HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "host_id": "h1",
  "ip": "10.0.0.1",
  "hostname": "host-1",
  "mac": "00:00:00:00:00:01"
}
```

#### Конфигурация маршрутизатора

```http
POST /host/router_save_config HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "router_id": "r1",
  "ips": ["10.0.0.1", "10.0.1.1"],
  "routing_table": [...]
}
```

#### Конфигурация свитча

```http
POST /host/switch_save_config HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "switch_id": "s1",
  "stp_enabled": true,
  "vlan_config": {...}
}
```

---

### Endpoints для эмуляции

#### Запуск симуляции

```http
POST /run_simulation HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "jobs": [
    {
      "host": "h1",
      "command": "ping -c 1 10.0.0.2"
    }
  ]
}
```

**Response (асинхронно через WebSocket или polling):**

```json
{
  "status": "running",
  "animation": [...],
  "pcaps": ["network.pcap"]
}
```

#### Проверка статуса симуляции

```http
GET /check_simulation?guid=550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
```

**Response:**

```json
{
  "status": "completed",
  "animation": [...],
  "metrics": {
    "latency": 5.2,
    "jitter": 0.3,
    "packet_loss": 0
  }
}
```

---

### Endpoints для аутентификации

#### Получить страницу входа

```http
GET /auth/login.html HTTP/1.1
```

#### Google OAuth redirect

```http
GET /auth/google_login HTTP/1.1
```

#### VK OAuth redirect

```http
GET /auth/vk_login HTTP/1.1
```

#### Выход из системы

```http
GET /auth/logout HTTP/1.1
```

#### Профиль пользователя

```http
GET /user/profile.html HTTP/1.1
```

---

## Работа с jobs (команды на хостах)

### Типы jobs

```python
job_types = {
    "ping": "ICMP ping",
    "traceroute": "Trace route to destination",
    "iperf": "Bandwidth test",
    "curl": "HTTP request",
    "custom": "Custom bash command"
}
```

### Endpoint для удаления job

```http
POST /host/delete_job HTTP/1.1
Content-Type: application/json

{
  "guid": "550e8400-e29b-41d4-a716-446655440000",
  "host_id": "h1",
  "job_id": "job_12345"
}
```

---

## HTTP Status Codes

| Код | Значение | Когда используется |
| ---- | ---------- | ------------------- |
| 200 | OK | Успешный запрос |
| 201 | Created | Создан новый ресурс |
| 400 | Bad Request | Неверный формат данных |
| 401 | Unauthorized | Требуется аутентификация |
| 403 | Forbidden | Доступ запрещен |
| 404 | Not Found | Ресурс не найден |
| 409 | Conflict | Конфликт (например, дубликат GUID) |
| 429 | Too Many Requests | Rate limiting |
| 500 | Internal Server Error | Ошибка сервера |
| 503 | Service Unavailable | Celery worker недоступен |

---

## Error Response Format

```json
{
  "error": "Description of error",
  "code": "ERROR_CODE",
  "details": {
    "field": "additional info"
  }
}
```

Пример:

```json
{
  "error": "Network not found",
  "code": "NETWORK_NOT_FOUND",
  "details": {
    "guid": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```
