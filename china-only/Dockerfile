FROM python:3.11-slim

LABEL org.opencontainers.image.title="FortiGate ALL-CN IP Updater" \
      org.opencontainers.image.description="Auto-update FortiGate Group_ALL-CN address group with China mainland IP ranges"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fortigate_cn_ip_updater.py .

RUN mkdir -p /app/backups /app/logs

# 运行时配置（通过 docker-compose 或 -e 覆盖）
# API_TOKEN 不在镜像内设置默认值，运行时通过 -e / compose 注入
ENV FW_HOST="" \
    FW_PORT="443" \
    VDOM="root" \
    UPDATE_TIME="03:00" \
    GROUP_NAME="Group_ALL-CN" \
    IP_SOURCE_URL="https://ispip.clang.cn/all_cn.txt" \
    MAX_WORKERS="20" \
    WECHAT_WEBHOOK=""

# 默认：启动即执行一次，然后每天定时更新
ENTRYPOINT ["python", "-u", "fortigate_cn_ip_updater.py"]
CMD ["--now"]
