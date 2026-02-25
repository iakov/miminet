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

**users**: id, username, email, password_hash, auth_provider, external_id, is_active, is_admin, created_at

**networks**: id, guid, author_id, name, nodes (JSONB), edges (JSONB), animation (JSONB), is_shared, created_at

**Quiz**: tests, sections, questions, answers, session_questions

### Индексы для оптимизации

```sql
CREATE INDEX idx_networks_author ON networks(author_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_auth ON users(auth_provider, external_id);
```

---

## 🌐 API Reference

### Networks

```text
POST   /create_network              {name, description}
GET    /web_network?guid=...        Получить сеть
POST   /delete_network              {guid}
POST   /post_network_nodes          {guid, nodes: [{type, id, name, ip}]}
POST   /post_nodes_edges            {guid, edges: [{source, target, bw, delay, loss}]}
POST   /move_network_nodes          {guid, nodes: [{id, x, y}]}
```

### Simulation

```text
POST   /run_simulation              {guid, jobs: [{host, command}]}
GET    /check_simulation?guid=...   Проверить статус
```

### Host Configuration

```text
POST   /host/save_config            {guid, host_id, ip, hostname, mac}
POST   /host/router_save_config     {guid, router_id, ips, routing_table}
POST   /host/switch_save_config     {guid, switch_id, stp_enabled, vlan_config}
POST   /edge/save_config            {guid, source, target, bw, delay, loss}
```

### Authentication

```text
GET    /auth/login.html             Страница входа
GET    /auth/google_login           Google OAuth
GET    /auth/vk_login               VK OAuth
GET    /auth/logout                 Выход
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
