# 🛠️ Разработка

## 📦 Управление зависимостями

- ✅ Единая конфигурация для всех окружений (`pyproject.toml`)
- ✅ Воспроизводимые сборки
- ✅ Четкое разделение dev и production зависимостей
- ✅ Отдельный группы зависимостей для компонент


## 🎨 Паттерны кода

### 1. Flask Route Pattern

```python
@app.route('/api/endpoint', methods=['POST'])
@login_required
def endpoint():
    data = request.get_json()
    if not data or 'field' not in data:
        return jsonify({'error': 'Invalid input'}), 400
    return jsonify(do_something(data, current_user)), 200
```

### 2. SQLAlchemy Model Pattern

```python
class Network(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    def to_dict(self):
        return {'id': self.id, 'name': self.name}
```

### 3. Celery Task Pattern

```python
@app.task(bind=True, max_retries=3)
def task_name(self, param):
    try:
        return do_work(param)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### 4. Mininet Emulation Pattern

```python
def emulate(network_json):
    net = Mininet()
    hosts = {n.name: net.addHost(n.name, ip=n.ip) for n in network_json.nodes}
    for e in network_json.edges:
        net.addLink(hosts[e.source], hosts[e.target], bw=e.bw, delay=f'{e.delay}ms')
    net.start()
    animation = collect_animation(net)
    net.stop()
    return animation
```

---

## 💡 Частые задачи

### Добавить новый API endpoint

1. **Создать функцию-обработчик** в соответствующем файле (`miminet_*.py`):

```python
def new_endpoint():
    """Beschreibung"""
    # Логика
    return jsonify(result), 200
```

2. **Зарегистрировать роут** в `front/src/app.py`:

```python
app.add_url_rule('/api/new_endpoint', methods=['POST'], view_func=new_endpoint)
```

3. **Добавить тесты** в `front/tests/test_*.py`

### Добавить новое поле в модель Network

1. **Обновить модель** в `front/src/miminet_model.py`:

```python
class Network(db.Model):
    new_field = db.Column(db.String(100))
```

2. **Создать миграцию**:

```bash
docker exec -it miminet bash
flask db migrate -m "Add new_field to Network"
flask db upgrade
```

3. **Обновить метод `to_dict()`** если нужно для JSON сериализации

### Добавить новый тип устройства

1. **Обновить схему валидации** в `back/src/network_schema.py`
2. **Добавить логику эмуляции** в `back/src/emulator.py`:
   - Создание устройства в `create_nodes()`
   - Конфигурация параметров
3. **Обновить UI** в `front/src/static/` и `templates/`

### Изменить параметры эмуляции

Файл: `back/src/emulator.py`, функция `emulate()`

Доступные параметры для `addLink()`:

- `bw`: Пропускная способность (Mbps)
- `delay`: Задержка (ms)
- `loss`: Потеря пакетов (%)
- `jitter`: Джиттер (ms)

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

### Организация кода в файле

1. Docstring модуля
2. Imports
3. Constants/Config
4. Classes (если есть)
5. Functions (в логическом порядке)
6. Main guard: `if __name__ == '__main__':`

---

## 🔍 Где искать информацию

### По функциональности

| Вопрос | Где искать |
| -------- | ----------- |
| Как создать сеть? | `front/src/miminet_network.py` |
| Как запустить симуляцию? | `front/src/miminet_simulation.py` + `back/src/emulator.py` |
| Как добавить устройство? | `front/src/miminet_host.py` |
| Как работает аутентификация? | `front/src/miminet_auth.py` |
| Как парсить пакеты? | `front/src/pcap_parser.py` + `back/src/pkt_parser.py` |
| Как работают тесты? | `front/tests/utils/networks.py` |

---

## ✅ Чек-лист перед коммитом

Перед коммитом убедитесь:

- [ ] Код следует соглашениям проекта (snake_case, docstrings)
- [ ] Добавлены/обновлены docstrings для новых функций
- [ ] Добавлены тесты для новой функциональности
- [ ] Все тесты проходят (`pytest`)
- [ ] Если изменилась модель БД - создана миграция
- [ ] Нет TODO/FIXME в коммите (если только intentional)
- [ ] Обновлена документация (если нужно)
- [ ] Убелись, что локально код работает
