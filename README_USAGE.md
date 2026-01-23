# 飞塔防火墙中国IP自动更新 - 使用指南

## 命令行参数

脚本现在支持以下运行模式：

### 1. 后台定时运行（推荐）
启动服务并在后台等待定时任务：
```bash
nohup python3 fortigate_cn_ip_updater.py > nohup.out 2>&1 &
```

### 2. 立即执行一次 + 后台定时运行
启动时立即执行一次更新，然后继续等待定时任务：
```bash
nohup python3 fortigate_cn_ip_updater.py --now > nohup.out 2>&1 &
```

### 3. 只执行一次（不启动定时任务）
适用于 cron 调用或手动测试：
```bash
python3 fortigate_cn_ip_updater.py --once
```

### 4. 前台交互运行（调试用）
前台运行，可以看到实时输出：
```bash
python3 fortigate_cn_ip_updater.py --now
```

## 常用操作

### 查看运行状态
```bash
# 查看进程是否运行
ps aux | grep fortigate_cn_ip_updater

# 查看实时日志
tail -f nohup.out

# 查看详细日志
tail -f logs/cn_ip_update_$(date +%Y%m%d).log
```

### 停止服务
```bash
# 找到进程ID
ps aux | grep fortigate_cn_ip_updater

# 停止进程
kill <进程ID>

# 或强制停止
pkill -f fortigate_cn_ip_updater
```

### 重启服务
```bash
# 停止旧进程
pkill -f fortigate_cn_ip_updater

# 启动新进程
nohup python3 fortigate_cn_ip_updater.py --now > nohup.out 2>&1 &
```

## 使用 systemd 服务（推荐方案）

### 1. 创建服务文件
编辑 `/etc/systemd/system/fortigate-updater.service`:
```ini
[Unit]
Description=FortiGate CN IP Auto Updater
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/fortigate-updater
ExecStart=/usr/bin/python3 /opt/fortigate-updater/fortigate_cn_ip_updater.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. 安装并启动服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable fortigate-updater
sudo systemctl start fortigate-updater
```

### 3. 管理服务
```bash
# 查看状态
sudo systemctl status fortigate-updater

# 查看日志
sudo journalctl -u fortigate-updater -f

# 重启服务
sudo systemctl restart fortigate-updater

# 停止服务
sudo systemctl stop fortigate-updater
```

## 使用 cron 定时任务（简单方案）

如果不想脚本一直运行，可以用 cron 每天定时调用：

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天凌晨3点执行）
0 3 * * * cd /opt/fortigate-updater && /usr/bin/python3 fortigate_cn_ip_updater.py --once >> /var/log/fortigate-update.log 2>&1
```

## 立即手动更新

如果需要立即手动执行一次更新（不影响定时任务）：
```bash
cd /opt/fortigate-updater
python3 fortigate_cn_ip_updater.py --once
```

## 日志文件位置

- **nohup日志**: `nohup.out`
- **详细日志**: `logs/cn_ip_update_YYYYMMDD.log`
- **备份文件**: `backups/backup_YYYYMMDD_HHMMSS.json`

## 企业微信通知

更新完成后会自动发送企业微信通知，包含：
- 更新时间
- 耗时
- 成功/失败统计
- 各运营商详细信息

## 故障排查

### 脚本无法启动
```bash
# 检查Python版本（需要3.6+）
python3 --version

# 检查依赖
pip3 install -r requirements.txt

# 检查配置
python3 -c "import fortigate_cn_ip_updater; print('OK')"
```

### 更新失败
```bash
# 查看详细错误日志
tail -100 logs/cn_ip_update_$(date +%Y%m%d).log

# 检查网络连接
curl -I https://ispip.clang.cn/cmcc.txt

# 检查防火墙连接
curl -k https://10.4.0.1:8443
```

### 定时任务不执行
```bash
# 确认进程运行
ps aux | grep fortigate_cn_ip_updater

# 检查日志
tail -f nohup.out
```

## 配置修改

编辑 `fortigate_cn_ip_updater.py` 中的 CONFIG 部分：
- `FW_HOST`: 防火墙IP
- `FW_PORT`: 防火墙端口
- `API_TOKEN`: API令牌
- `UPDATE_TIME`: 更新时间（24小时制，如 '03:00'）
- `WECHAT_WEBHOOK`: 企业微信机器人URL
- `MAX_WORKERS`: 并发线程数

修改后需重启服务生效。
