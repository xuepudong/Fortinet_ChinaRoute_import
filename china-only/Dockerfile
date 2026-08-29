# 多架构镜像（linux/amd64 + linux/arm64）
# 构建: docker buildx build --platform linux/amd64,linux/arm64 -t <user>/fortigate-cn-updater:latest --push .
FROM python:3.11-slim

# BuildKit 自动注入，仅用于日志/标签，不影响构建内容
ARG TARGETPLATFORM
ARG VERSION=dev
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="FortiGate ALL-CN IP Updater" \
      org.opencontainers.image.description="Auto-update the FortiGate Group_ALL-CN address group with China mainland IP ranges" \
      org.opencontainers.image.source="https://github.com/xuepudong/Fortinet_ChinaRoute_import" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fortigate_cn_ip_updater.py .

# 以 root 运行：脚本需要写入 /app/logs 与 /app/backups，
# 而这两个目录通常是宿主机 bind mount，非 root 用户会因属主不符而写入失败
RUN mkdir -p /app/backups /app/logs

# 运行时配置（通过 docker-compose 或 -e 覆盖）
# API_TOKEN 不设默认值，避免写入镜像元数据
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
