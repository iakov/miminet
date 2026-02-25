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

### Запуск тестов

Для подробных инструкций см. [03-TESTING.md](03-TESTING.md).

```bash
# Frontend (Selenium)
cd front/tests && pytest . -v

# Backend (pytest, требует sudo)
cd back/tests && sudo pytest . -v
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

## Полезные команды

Для полного списка команд см. [CLAUDE.md](../CLAUDE.md#-ключевые-команды).

```bash
# Основные
docker ps && docker logs -f miminet
docker-compose down -v && ./start_all_containers.sh
flask db upgrade && pytest . -v
```

---

## Проверка работоспособности

- [ ] `docker ps` показывает все контейнеры
- [ ] `http://localhost` открывается
- [ ] Можно создать сеть и запустить симуляцию
- [ ] Тесты запускаются: `pytest front/tests -v` и `pytest back/tests -v`
