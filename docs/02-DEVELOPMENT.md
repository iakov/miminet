# 🛠️ Разработка

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
