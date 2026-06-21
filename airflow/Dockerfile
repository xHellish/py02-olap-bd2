FROM apache/airflow:2.10.4
# Agregar airflow al grupo root (GID 0) para acceder al Docker socket en Docker Desktop
# El socket /var/run/docker.sock está owned por root:root (srw-rw----)
USER root
RUN usermod -aG root airflow
# Instalar paquetes como usuario airflow (requerimiento de Airflow)
USER airflow
RUN pip install --no-cache-dir docker>=7.0.0 psycopg2-binary elasticsearch
