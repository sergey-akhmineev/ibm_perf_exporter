#!/bin/bash
set -e

# Установка зависимостей для парсинга toml (используем Python для извлечения)
parse_toml() {
  python3 - <<EOF
import tomllib, os

try:
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)
except FileNotFoundError:
    exit("Конфигурационный файл 'config.toml' не найден.")
except Exception as e:
    exit(f"Ошибка при чтении конфигурационного файла: {e}")

main = config.get('main', {})

# Экспорт переменных окружения
print(f"SSH_USER={main.get('SSH_USER', '')}")
print(f"SSH_HOST={main.get('SSH_HOST', '')}")
print(f"SSH_PASSWORD={main.get('SSH_PASSWORD', '')}")
print(f"REMOTE_DIR={main.get('REMOTE_DIR', '/dumps/iostats')}")
print(f"LOCAL_DIR={main.get('LOCAL_DIR', '/app/iostats')}")
print(f"INTERVAL={main.get('INTERVAL', 60)}")
EOF
}

# Экспортируем переменные
export $(parse_toml)

# Проверка обязательных переменных
if [ -z "$SSH_USER" ] || [ -z "$SSH_HOST" ] || [ -z "$SSH_PASSWORD" ]; then
  echo "Ошибка: SSH_USER, SSH_HOST или SSH_PASSWORD не установлены в config.toml."
  exit 1
fi

# Создание локальной директории, если она не существует
mkdir -p "$LOCAL_DIR"

# Запуск экспортера
echo "Запуск экспортера..."
python3 exporter.py &
EXPORTER_PID=$!

# Обработчики сигналов для корректного завершения
trap "echo 'Остановка экспортера...' ; kill $EXPORTER_PID ; exit 0" SIGTERM SIGINT

# Основной цикл копирования и обработки файлов
while true; do
  echo "Копирование файлов с удалённого сервера..."
  sshpass -p "$SSH_PASSWORD" scp -o StrictHostKeyChecking=no "${SSH_USER}@${SSH_HOST}:${REMOTE_DIR}*" "${LOCAL_DIR}/" || {
    echo "Ошибка: Не удалось скопировать файлы с удалённого сервера."
  }

  sleep "$INTERVAL"
done