# 🚀 Как запустить проект

## Быстрый старт (Docker)

### 1. Клонировать репозиторий

```bash
git clone git@github.com:mimi-net/miminet.git
cd miminet
```

### 2. Настроить файлы конфигурации

**Скопировать OAuth конфиг:**

```bash
# Получить vk_auth.json и скопировать в front/src/
cp vk_auth.json front/src/
```

**Создать секретный ключ:**

```bash
# Создать файл miminet_secret.conf в front/src/ с случайной строкой
echo "your_random_secret_key_here" > front/src/miminet_secret.conf
```

### 3. Запустить все контейнеры

```bash
./start_all_containers.sh
```

### 4. Открыть в браузере

```
http://localhost
```

---

## Миграции БД

### Проверить статус миграций

```bash
docker exec -it miminet bash
flask db current   # Текущая версия БД
flask db history   # История всех миграций
```

### Создать новую миграцию (если изменилась модель)

```bash
docker exec -it miminet bash
flask db migrate -m "Description of changes"
flask db upgrade
```

### Откатить миграцию

```bash
docker exec -it miminet bash
flask db downgrade  # На одну версию назад
flask db downgrade base  # Откатить полностью
```

---

## Запуск тестов

### Frontend тесты (Selenium)

**Структура тестов:**

```text
front/tests/
├── conftest.py          # Pytest fixtures
├── utils/
│   ├── locators.py      # Веб-элементы (XPATH, CSS)
│   ├── networks.py      # Классы для создания тестовых сетей
│   └── checkers.py      # Проверка корректности эмуляции
└── test_*.py            # Тестовые сценарии
```

**Запуск тестов:**

```bash
cd front/tests
sh docker/run.sh  # Запуск контейнеров с браузерами
pytest front/tests -v  # Verbose вывод
pytest front/tests -k test_name  # Конкретный тест
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

**Структура тестов:**

```text
back/tests/
├── test_json/           # JSON конфигурации для тестов
│   ├── simple.json
│   └── complex.json
└── test_*.py            # Unit тесты
```

**Запуск тестов (требует root для Mininet):**

```bash
cd back/tests
sudo bash  # Mininet требует root
source .venv/bin/activate
export PYTHONPATH=$PYTHONPATH:../src
pytest . -v
pytest . -k test_name  # Конкретный тест
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

## Проблемы при запуске

### База данных не мигрирует

**Проблема**: Старая миграция или неправильный `MODE`

**Решение:**

```bash
# Проверить MODE в .env (должен быть MODE=dev)
docker exec -it miminet bash

# Пересоздать миграции
rm -rf migrations/
flask db init
flask db migrate
flask db upgrade
```

### Mininet не запускается

**Проблема**: Mininet требует нативный Linux kernel (не работает на WSL)

**Решение:**

- Используйте Docker на Linux хосте
- Или используйте Vagrant с VirtualBox/VMware
- Или используйте нативный Linux

### Контейнеры не поднимаются

**Решение:**

```bash
# Пересоздать контейнеры
docker-compose down -v  # -v удалит все volumes
./start_all_containers.sh

# Или проверить логи
docker logs -f miminet  # Flask logs
docker logs -f celery   # Celery logs
docker logs -f rabbitmq # RabbitMQ logs
```

---

## Полезные команды Docker

```bash
# Контейнеры и логи
docker ps                          # Список запущенных контейнеров
docker ps -a                       # Все контейнеры (включая停止ленные)
docker exec -it miminet bash       # SSH в контейнер
docker logs -f miminet             # Следить за логами
docker logs --tail 100 miminet     # Последние 100 строк

# Управление
docker-compose restart             # Перезагрузить контейнеры
docker-compose stop                # Остановить
docker-compose start               # Запустить
docker-compose down -v             # Полностью остановить и удалить volumes

# Очистка
docker system prune -a             # Очистить неиспользуемые образы
docker container prune             # Удалить stopped контейнеры
```

---

## Полезные команды БД

```bash
docker exec -it miminet bash

# Миграции
flask db migrate -m "message"      # Создать миграцию
flask db upgrade                   # Применить миграции
flask db downgrade                 # Откатить миграцию
flask db current                   # Текущая версия
flask db history                   # История миграций

# Работа с PostgreSQL
psql -U postgres -h postgres miminet  # Подключиться к БД
# SELECT * FROM users; (внутри psql)
# \dt (вывести все таблицы)
# \q (выход)
```

---

## Чек-лист для проверки

Перед тем как заявить, что локальный запуск работает:

- [ ] Контейнер Flask поднялся (`docker ps` shows miminet)
- [ ] База данных мигрировала (`docker logs miminet` показывает успех)
- [ ] Celery worker запустился (`docker logs celery` shows готовность)
- [ ] RabbitMQ доступен для управления (`http://localhost:15672` guest/guest)
- [ ] Приложение открывается (`http://localhost`)
- [ ] Можно создать сеть и запустить симуляцию
- [ ] Фронтенд тесты проходят (или хотя бы запускаются)
