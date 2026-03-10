# 🧪 Тестирование

## Frontend тесты (Selenium)

### Структура тестов

```text
front/tests/
├── conftest.py          # Pytest fixtures (driver, login, test data)
├── utils/
│   ├── locators.py      # Локаторы веб-элементов (XPATH, CSS)
│   ├── networks.py      # Helper классы для создания тестовых сетей
│   └── checkers.py      # Функции для проверки результатов эмуляции
└── test_*.py            # Тестовые сценарии
    ├── test_basic.py
    ├── test_device_configure_names.py
    ├── test_vlan.py
    └── ... (30+ тестовых файлов)
```

### Установка зависимостей

```bash
# Через uv (рекомендуется)
uv sync --group frontend --group dev-frontend

# Или через Docker
docker exec -it miminet bash
uv sync --group frontend --group dev-frontend
```

### Запуск тестов

**Все тесты:**

```bash
cd front/tests
pytest . -v
```

**Конкретный тест:**

```bash
pytest test_basic.py::test_create_simple_network -v
```

**Тесты с определенным названием:**

```bash
pytest -k "vlan" -v  # Все тесты, содержащие "vlan"
```

**С видео-отчетом:**

```bash
pytest . --video=all  # Записать все тесты
pytest . --video=failed  # Только падающие тесты
```

### Написание теста (пример)

```python
import pytest
from utils.networks import TwoHostsNetwork

def test_create_simple_network(driver, login):
    """Проверка создания простой сети с двумя хостами."""
    
    # Инициализация паттерна сети
    network = TwoHostsNetwork(driver)
    
    # Создание сети через UI
    network.create()
    
    # Запуск симуляции
    network.run_simulation()
    
    # Проверка результатов
    assert network.check_connectivity()
    assert network.get_animation_frames() > 0
```

### Структура Selenium test fixtures

```python
# conftest.py

@pytest.fixture
def driver():
    """Инициализация WebDriver (Chrome/Firefox)."""
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()

@pytest.fixture
def login(driver):
    """Автоматический вход в систему перед тестом."""
    driver.get("http://localhost/auth/login")
    # Ввод учетных данных и вход
    # Возврат объекта текущего пользователя
    return current_user
```

### Типичные assertions

```python
# Проверка видимости и текста
assert "Network created" in driver.page_source

# Проверка количества элементов
nodes = driver.find_elements(By.CLASS_NAME, "network-node")
assert len(nodes) == 2  # 2 хоста

# Проверка анимации
animation_data = json.loads(driver.execute_script(
    "return sessionStorage.getItem('animation')"
))
assert len(animation_data) > 0
```

---

## Backend тесты (pytest)

### Структура тестов

```text
back/tests/
├── __init__.py
├── pytest.ini          # Конфигурация pytest
├── test_miminet_back.py # Основные тесты эмуляции
├── test_duplication.py  # Тесты на дублирование пакетов
├── test_json/          # JSON конфигурации для тестов
│   ├── simple.json      # Две хосты, одна связь
│   ├── complex.json     # Сложная топология
│   └── ... (другие конфиги)
└── network_examples_json/ # Примеры различных топологий
    ├── vlan_network.json
    ├── router_network.json
    └── ...
```

### Требования для запуска

```bash
# Linux (требует root для Mininet)
sudo bash
cd back/tests

# Установить зависимости через uv
uv sync --group backend --group dev-backend

# Установить переменную PYTHONPATH
export PYTHONPATH=$PYTHONPATH:../src
```

### Запуск тестов

```bash
# Все тесты
pytest . -v

# Конкретный тест
pytest test_miminet_back.py::test_emulation_two_hosts -v

# Тесты по паттерну имени
pytest -k "duplication" -v

# С выводом stdout
pytest . -s

# Только фейлы из последнего запуска
pytest --lf

# Только фейлы и exit on first fail
pytest --ff -x
```

### Написание теста (пример)

```python
import json
from emulator import emulate
from network_schema import NetworkSchema

def test_emulation_two_hosts(tmpdir):
    """Проверка эмуляции простой сети."""
    
    # Подготовка конфигурации
    with open('test_json/simple.json') as f:
        network_data = json.load(f)
    
    # Валидация схемы
    schema = NetworkSchema()
    network = schema.load(network_data)
    
    # Запуск эмуляции
    animation, pcaps = emulate(network)
    
    # Assertions
    assert animation is not None
    assert len(animation) > 0  # Есть пакеты в анимации
    assert len(pcaps) > 0      # Есть pcap файлы
    assert pcaps[0].endswith('.pcap')
```

### Backend fixtures

```python
@pytest.fixture
def simple_network():
    """Загрузить конфигурацию сети."""
    with open('test_json/simple.json') as f:
        return json.load(f)
```

### Backend assertions

```python
assert isinstance(animation, list) and len(animation) > 0
assert isinstance(pcaps, list) and len(pcaps) > 0
frame = animation[0]
assert all(k in frame for k in ['source', 'target', 'timestamp'])
```

---

## Известные проблемы с тестами

### Mininet иногда падает с ошибкой

**Проблема**: Intermittent failures из-за race conditions  
**Решение**: В `back/src/tasks.py` реализован retry механизм (4 попытки)

```python
for _ in range(4):
    try:
        animation, pcaps = emulate(network_json)
        return json.dumps(animation), pcaps
    except Exception as e:
        logger.error(e)
        continue
```

### Selenium timeouts

**Проблема**: Тест ждет элемента, которого нет на странице

**Решение**: Увеличить таймаут в conftest:

```python
driver.implicitly_wait(10)  # 10 секунд
# Или явный wait:
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "element-id"))
)
```

### Тесты работают локально, но не в CI

**Проблема**: Разница в окружении (версии браузеров, Mininet)

**Решение**: Использовать контейнеры для воспроизведения окружения

```bash
docker-compose -f docker-compose.test.yml up
```

---

## CI/CD Testing Pipeline

### Типичные этапы

1. **code-style** (eslint, flake8, black)
2. **unit-tests** (backend pytest)
3. **integration-tests** (Mininet эмуляция)
4. **selenium-tests** (frontend UI)
5. **security-scan** (SAST, dependency check)

### GitHub Actions пример

```yaml
name: Tests
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pytest back/tests -v
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pytest front/tests -v
```

---

## Генерирование test coverage

### Для Python (backend)

```bash
# pytest-cov уже включен в dev зависимости
uv run pytest back/tests --cov=back/src --cov-report=html
# Открыть htmlcov/index.html в браузере
```

### Для JavaScript (frontend)

```bash
npm test -- --coverage
```

---

## Best Practices

✅ Тесты независимы | Используйте fixtures | Тестируйте edge cases  
✅ Информативные assert'ы | Очищайте resources  
❌ Не hardcoding пути | Не пустые тесты | Не игнорируйте флакующие тест
