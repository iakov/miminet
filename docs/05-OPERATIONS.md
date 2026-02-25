# ⚙️ Операции и отладка

## 🔍 Debugging Tips

### Логирование

#### Frontend (Flask)

```bash
# Следить за логами
docker logs -f miminet

# Последние 100 строк
docker logs --tail 100 miminet

# С временными метками
docker logs -f --timestamps miminet
```

#### Backend (Celery)

```bash
# Следить за работником
docker logs -f celery

# Проверить очередь задач
docker exec -it celery celery -A tasks inspect active
```

#### RabbitMQ

```bash
# Management UI (username: guest, password: guest)
http://localhost:15672

# Проверить очереди
docker exec -it rabbitmq rabbitmqctl list_queues

# Очистить очередь
docker exec -it rabbitmq rabbitmqctl purge_queue queue_name
```

### Python Debugger

#### Flask

```python
import pdb; pdb.set_trace()  # Breakpoint
```

#### Loggers

```python
import logging

logger = logging.getLogger(__name__)
logger.debug("Debug message")
logger.info("Info message")
logger.error("Error message")
```

### Mininet Debug Mode

```python
from mininet.log import setLogLevel

setLogLevel('debug')  # Verbose вывод
# или
setLogLevel('info')
setLogLevel('warning')
```

---

## 🐛 Известные проблемы и решения

### Mininet иногда падает с ошибкой

**Проблема**: Intermittent failures из-за race conditions или нехватки ресурсов

**Решение**:

1. Проверить доступную память:

```bash
docker stats  # Смотреть использование памяти
```

2. Retry механизм уже реализован в `back/src/tasks.py`:

```python
for _ in range(4):  # 4 попытки
    try:
        animation, pcaps = emulate(network_json)
        return json.dumps(animation), pcaps
    except Exception as e:
        logger.error(f"Attempt failed: {e}")
        continue
```

3. Устранить неполадки:

```bash
# Перезагрузить worker
docker restart celery

# Очистить очередь
docker exec -it rabbitmq rabbitmqctl purge_queue celery
```

### WSL не поддерживается для backend

**Проблема**: Mininet требует нативный Linux kernel (не работает на WSL1)

**Поддерживаемые варианты**:

- ✅ Docker на Linux хосте
- ✅ Vagrant с VirtualBox/VMware
- ✅ Нативный Linux
- ✅ WSL2 с Docker Desktop
- ❌ WSL1

**Решение для WSL2**:

```bash
# Убедиться, что Docker использует WSL2
docker --version
# Проверить статус WSL
wsl -l -v
```

### База данных не мигрирует

**Проблема**: Старая миграция, неправильный MODE, или corruption

**Решение:**

```bash
docker exec -it miminet bash

# Проверить MODE в .env
echo $MODE  # Должен быть MODE=dev

# Пересоздать миграции (ВНИМАНИЕ: потеря данных!)
rm -rf migrations/
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Или откатить последнюю миграцию:
flask db downgrade
```

### Контейнеры не поднимаются

**Проблема**: Порты заняты, неверная конфигурация, или недостаточно ресурсов

**Решение:**

```bash
# Проверить занятые порты
lsof -i :80      # Port 80
lsof -i :5432    # PostgreSQL
lsof -i :5672    # RabbitMQ
lsof -i :15672   # RabbitMQ Management

# Пересоздать контейнеры
docker-compose down -v  # -v удалит все volumes
./start_all_containers.sh

# Проверить логи
docker logs miminet
docker logs postgres
docker logs rabbitmq
docker logs celery
```

### Selenium timeouts в тестах

**Проблема**: Браузер не находит элемент или он загружается слишком долго

**Решение:**

```python
# conftest.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Явное ожидание
element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "element-id"))
)

# Или неявное (глобальное)
driver.implicitly_wait(10)  # 10 секунд на все find_element()
```

---

## 🔊 Логирование и мониторинг

### Уровни логирования

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
```

### Рекомендуемые уровни

- `DEBUG`: Детальная информация для di agnostics
- `INFO`: Подтверждение, что все работает как ожидается
- `WARNING`: Что-то неожиданное (default для большинства логгеров)
- `ERROR`: Ошибка, функция не выполнена
- `CRITICAL`: Серьезная ошибка, программа может упасть

### Просмотр логов в Docker

```bash
# Real-time logs
docker logs -f <container-name>

# Last N lines
docker logs --tail 50 <container-name>

# With timestamps
docker logs --timestamps <container-name>

# Filter by time (after specific time)
docker logs --since 10m <container-name>
```

---

## 🎓 Обучающие материалы

### Для новых разработчиков

- Прочитать README.md и CLAUDE.md
- Прочитать [00-ARCHITECTURE.md](00-ARCHITECTURE.md) для понимания системы
- Запустить проект локально через `./start_all_containers.sh`
- Создать тестовую сеть через UI
- Запустить симуляцию
- Изучить [front/src/app.py](../front/src/app.py) (Flask endpoints)
- Изучить [back/src/emulator.py](../back/src/emulator.py) (Mininet логика)
- Написать простой тест в [front/tests/](../front/tests/)
- Или добавить тест backend в [back/tests/](../back/tests/)
- Добавить новый API endpoint
- Или исправить существующий баг

### Порядок учебного чтения

1. [CLAUDE.md](../CLAUDE.md) (этот файл) — быстрая навигация
2. [00-ARCHITECTURE.md](00-ARCHITECTURE.md) — архитектура проекта
3. [01-GETTING_STARTED.md](01-GETTING_STARTED.md) — как запустить
4. [front/src/app.py](../front/src/app.py) — Flask endpoints
5. [back/src/emulator.py](../back/src/emulator.py) — Mininet эмуляция
6. [front/src/miminet_model.py](../front/src/miminet_model.py) — БД модели
7. [03-TESTING.md](03-TESTING.md) — как писать тесты

---

## 📚 Дополнительные ресурсы

### Официальная документация

- [Mininet Documentation](http://mininet.org/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy ORM Guide](https://docs.sqlalchemy.org/en/20/orm/)
- [Celery Task Queue](https://docs.celeryproject.org/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)
- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Manual](https://www.postgresql.org/docs/)

### Релевантные проекты

- [GitHub: Mininet](https://github.com/mininet/mininet)
- [GitHub: ipmininet](https://github.com/cnp3/ipmininet)
- [PyPI: Flask-Migrate](https://pypi.org/project/Flask-Migrate/)
- [PyPI: SQLAlchemy](https://pypi.org/project/SQLAlchemy/)

### Полезные команды

```bash
# Docker
docker ps -a                       # Все контейнеры
docker exec -it <name> bash        # SSH в контейнер
docker logs -f <name>              # Логи
docker-compose restart             # Перезапуск
docker system prune -a             # Очистка

# Database
flask db migrate -m "message"      # Миграция
flask db upgrade                   # Применить
flask db downgrade                 # Откатить
flask db history                   # История

# Tests
pytest . -v                        # Все тесты
pytest . -k "pattern" -v           # По паттерну
pytest --lf                        # Только фейлы
pytest --cov=module --cov-report=html  # Coverage

# Git
git log --oneline                  # История коммитов
git diff HEAD~1                    # Изменения с прошлого коммита
git status                         # Статус
```

---

## 🆘 Получение помощи

### Внутренние ресурсы

| Вопрос | Ресурс |
| -------- | --------- |
| Как создать сеть? | [02-DEVELOPMENT.md](02-DEVELOPMENT.md#add-new-api-endpoint) |
| Как запустить симуляцию? | [01-GETTING_STARTED.md](01-GETTING_STARTED.md) |
| Как добавить устройство? | [00-ARCHITECTURE.md](00-ARCHITECTURE.md#key-files) |
| Как писать тесты? | [03-TESTING.md](03-TESTING.md) |
| Как работает БД? | [04-DATABASE_AND_API.md](04-DATABASE_AND_API.md) |
| Как отладить ошибку? | Этот файл (Debugging section) |

### Внешние ресурсы

- **GitHub Issues**: https://github.com/mimi-net/miminet/issues
- **GitHub Discussions**: https://github.com/mimi-net/miminet/discussions
- **Документация проекта**: https://github.com/mimi-net/miminet#readme

### Структура issue в GitHub

```markdown
**Describe the bug**
A clear description of what happened.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
What you expected to happen.

**Environment**
- OS: [e.g. Ubuntu 20.04]
- Python: [e.g. 3.9]
- Docker: [yes/no]

**Logs and Screenshots**
Attach relevant logs and screenshots.
```

---

## ✅ Finalization Checklist

Перед тем как решить, что готово:

- [ ] Функциональность работает локально
- [ ] Все тесты проходят (backend и frontend)
- [ ] Код следует соглашениям проекта
- [ ] Docstrings обновлены
- [ ] Миграции БД применены (если нужны)
- [ ] Логирование на месте
- [ ] Обновлена документация
- [ ] Нет TODO/FIXME комментариев
- [ ] Коммит message информативный

---

## 📞 Контакты

- **GitHub**: https://github.com/mimi-net/miminet
- **Website**: https://miminet.ru/

---

**Последнее обновление**: Февраль 2026  
**Версия**: 1.0  
**Статус**: ✅ Готово к использованию
