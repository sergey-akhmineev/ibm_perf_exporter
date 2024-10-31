FROM python:3.10-slim-bullseye

# Установим необходимые пакеты: bash, sshpass, scp (openssh), и другие зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash sshpass openssh-client


# Установим рабочую директорию
WORKDIR /app

## Копируем requirements.txt и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt


## Копируем все остальные файлы
COPY entrypoint.sh exporter.py config.toml ./

# Делаем entrypoint.sh исполняемым
RUN chmod +x /app/entrypoint.sh

# Указываем entrypoint
ENTRYPOINT ["./entrypoint.sh"]