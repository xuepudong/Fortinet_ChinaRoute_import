FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fortigate_cn_ip_updater.py .

RUN mkdir -p /app/backups /app/logs

ENV FW_HOST=""
ENV FW_PORT="443"
ENV VDOM="root"
ENV UPDATE_TIME="03:00"

CMD ["python", "-u", "fortigate_cn_ip_updater.py"]
