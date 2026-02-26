# 🎯 Miminet — навигатор документации

**Miminet** — веб-эмулятор компьютерных сетей на базе Mininet для образовательных целей.

## 🚀 Быстрая навигация

| Раздел | Содержание | Когда использовать |
| -------- | ----------- | ------------------- |
| **[🏗️ ARCHITECTURE](docs/00-ARCHITECTURE.md)** | Архитектура, структура проекта, ключевые файлы, технологический стек | Понимание как работает система |
| **[🚀 GETTING_STARTED](docs/01-GETTING_STARTED.md)** | Запуск проекта, миграции БД, первые шаги | Новые разработчики, локальный запуск |
| **[🛠️ DEVELOPMENT](docs/02-DEVELOPMENT.md)** | Паттерны кода, частые задачи, соглашения, чек-лист | Написание кода, создание features |
| **[🧪 TESTING](docs/03-TESTING.md)** | Тестирование (frontend Selenium, backend pytest) | Написание и запуск тестов |
| **[📊 DATABASE_AND_API](docs/04-DATABASE_AND_API.md)** | БД схема, API endpoints, безопасность | Работа с данными, интеграции |
| **[⚙️ OPERATIONS](docs/05-OPERATIONS.md)** | Debugging, troubleshooting, обучение, ресурсы | Отладка проблем, получение помощи |

---

## 📋 Основная информация

**Функциональность:**

- ✅ Визуальное создание сетевых топологий (drag & drop)
- ✅ Эмуляция сетей с использованием Mininet
- ✅ Сбор метрик и анимация передачи пакетов
- ✅ Анализ pcap файлов
- ✅ Система квизов для самообучения

**Стек технологий:**

- Frontend: Flask, SQLAlchemy, Celery
- Backend: Mininet, ipmininet, dpkt
- Infrastructure: PostgreSQL 15, Redis 7, RabbitMQ 3, Docker, Nginx
- Package Management: uv (dependency management & lock files)
- Code Style: pre-commit hooks and CI lint with: black and mypy for Python code, and hadolint for Dockerfile(s)

**Где начать:**

1. **Новый разработчик?** → читай [01-GETTING_STARTED.md](docs/01-GETTING_STARTED.md)
2. **Понять архитектуру?** → читай [00-ARCHITECTURE.md](docs/00-ARCHITECTURE.md)
3. **Написать код?** → читай [02-DEVELOPMENT.md](docs/02-DEVELOPMENT.md)
4. **Написать тесты?** → читай [03-TESTING.md](docs/03-TESTING.md)
5. **Отладить проблему?** → читай [05-OPERATIONS.md](docs/05-OPERATIONS.md)

---

## 📂 Краткая структура проекта

```text
miminet/
├── docs/                       # 📚 ДОКУМЕНТАЦИЯ (читай эту папку!)
│   ├── 00-ARCHITECTURE.md      # Архитектура и структура
│   ├── 01-GETTING_STARTED.md   # Запуск проекта
│   ├── 02-DEVELOPMENT.md       # Разработка и паттерны
│   ├── 03-TESTING.md           # Тестирование
│   ├── 04-DATABASE_AND_API.md  # БД и API
│   └── 05-OPERATIONS.md        # Операции и отладка
│
├── front/                      # Frontend (Flask)
│   ├── src/
│   │   ├── app.py             # Flask entry point
│   │   ├── miminet_*.py       # Модули функциональности
│   │   └── ...
│   └── tests/                  # Selenium тесты
│
├── back/                       # Backend (Celery + Mininet)
│   ├── src/
│   │   ├── tasks.py           # Celery worker entry point
│   │   ├── emulator.py        # Mininet эмуляция (ЯДРО)
│   │   └── ...
│   └── tests/                  # pytest тесты
│
├── README.md
├── CLAUDE.md                   # 👈 Этот файл (навигация)
└── start_all_containers.sh
```

**Полная структура**: см. [00-ARCHITECTURE.md](docs/00-ARCHITECTURE.md#-структура-проекта)

---

## 🎓 Для новых разработчиков

Рекомендуемый порядок изучения:

1. **Этот файл** (обзор в 5 минут)
2. **[01-GETTING_STARTED.md](docs/01-GETTING_STARTED.md)** (запуск локально)
3. **[00-ARCHITECTURE.md](docs/00-ARCHITECTURE.md)** (понимание системы)
4. **[02-DEVELOPMENT.md](docs/02-DEVELOPMENT.md)** (паттерны и код)
5. **[03-TESTING.md](docs/03-TESTING.md)** (тесты)
6. **[04-DATABASE_AND_API.md](docs/04-DATABASE_AND_API.md)** (БД и API)
7. **[05-OPERATIONS.md](docs/05-OPERATIONS.md)** (отладка)

---

## 🔗 Быстрые ссылки

### Для фронтенда

- **Точка входа**: [front/src/app.py](front/src/app.py)
- **Модели БД**: [front/src/miminet_model.py](front/src/miminet_model.py)
- **Управление сетями**: [front/src/miminet_network.py](front/src/miminet_network.py)
- **Запуск симуляций**: [front/src/miminet_simulation.py](front/src/miminet_simulation.py)
- **Аутентификация**: [front/src/miminet_auth.py](front/src/miminet_auth.py)

### Для бэкенда

- **Celery worker**: [back/src/tasks.py](back/src/tasks.py)
- **Эмуляция Mininet** (ЯДРО): [back/src/emulator.py](back/src/emulator.py)
- **Топология сети**: [back/src/network.py](back/src/network.py)
- **Валидация схемы**: [back/src/network_schema.py](back/src/network_schema.py)

### Для тестирования

- **Frontend тесты**: [front/tests/](front/tests/)
- **Backend тесты**: [back/tests/](back/tests/)
- **Selenium тесты**: [front/tests/utils/](front/tests/utils/)
- **⚙️ Конфиг**: [pyproject.toml](pyproject.toml)

---

## 📞 Получение помощи

| Вопрос | Ресурс |
| -------- | --------- |
| Как запустить? | [01-GETTING_STARTED.md](docs/01-GETTING_STARTED.md) |
| Как работает? | [00-ARCHITECTURE.md](docs/00-ARCHITECTURE.md) |
| Как писать код? | [02-DEVELOPMENT.md](docs/02-DEVELOPMENT.md) |
| Как писать тесты? | [03-TESTING.md](docs/03-TESTING.md) |
| Как работает БД? | [04-DATABASE_AND_API.md](docs/04-DATABASE_AND_API.md) |
| Как отладить? | [05-OPERATIONS.md](docs/05-OPERATIONS.md) |
| Какие зависимости установить? | [DEPENDENCY_GROUPS_QUICK_REFERENCE.md](DEPENDENCY_GROUPS_QUICK_REFERENCE.md) |
art_all_containers.sh
docker exec -it miminet bash

# Миграции БД
flask db migrate -m "description"
flask db upgrade

# Тесты
pytest front/tests -v              # Frontend
pytest back/tests -v               # Backend

# Логи
docker logs -f miminet             # Flask
docker logs -f celery              # Celery worker
docker logs -f rabbitmq            # RabbitMQ
```

---

## ✅ Чек-лист для новичков

При первом запуске проверьте:

- [ ] Приложение доступно по http://localhost
- [ ] Можно создать тестовую сеть
- [ ] Можно запустить симуляцию
- [ ] Результаты сохраняются в БД
- [ ] Фронтенд тесты запускаются
- [ ] Backend тесты запускаются

---

**Последнее обновление**: Февраль 2026  
**Версия**: 1.0  
**Статус**: ✅ Готово к использованию

---

*CLAUDE.md — минимальная навигационная страница с ссылками на детальную документацию в папке `docs/`. Это уменьшает загружаемый контекст AI ассистентов при работе с проектом.*
