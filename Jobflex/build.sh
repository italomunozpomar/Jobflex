#!/usr/bin/env bash
# Exit on error
set -o errexit

apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev

curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list

apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17


pip install -r ../reqs.txt
python manage.py collectstatic --no-input
#python manage.py migrate