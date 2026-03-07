#!/bin/sh
#Starting all containers

SUDO=$(groups | grep -q docker && echo eval || echo sudo)

# Читаем MODE из front/.env, если не установлен в окружении
if [ -z "$MODE" ]; then
    if [ -f "front/.env" ]; then
        MODE=$(grep "^MODE=" front/.env | cut -d '=' -f2)
    fi
    # Если MODE все еще пустой, используем dev по умолчанию
    MODE="${MODE:-dev}"
fi

echo "[!] Starting containers in $MODE mode"

# Запуск backend (одинаковый для dev и prod)
cd back || exit
$SUDO docker compose up -d --build
cd ..

# Запуск frontend с выбором docker-compose файла
cd front || exit
if [ "$MODE" = "prod" ]; then
    echo "[!] Using docker-compose-prod.yml (Yandex Cloud PostgreSQL)"
    $SUDO docker compose -f docker-compose-prod.yml up -d --build
else
    echo "[!] Using docker-compose.yml (Local PostgreSQL)"
    $SUDO docker compose up -d --build
fi
cd ..

$SUDO docker ps -a
