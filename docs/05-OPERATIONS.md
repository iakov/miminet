# ⚙️ Операции и отладка

## 🔍 Debugging Tips

### Логирование

```bash
docker logs -f miminet    # Flask logs
docker logs -f celery     # Celery worker
docker logs -f rabbitmq   # RabbitMQ

# RabbitMQ Management UI: http://localhost:15672 (guest/guest)
docker exec -it rabbitmq rabbitmqctl list_queues
```

### Python Debugger

```python
import pdb; pdb.set_trace()          # Breakpoint
import logging
logger = logging.getLogger(__name__)
logger.debug|info|error("message")   # Log levels
```

### Mininet Debug

```python
from mininet.log import setLogLevel
setLogLevel('debug')  # or 'info', 'warning'
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

---

## 🆘 Получение помощи

Для вопросов и лучших практик см. [CLAUDE.md](../CLAUDE.md#-получение-помощи).

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
