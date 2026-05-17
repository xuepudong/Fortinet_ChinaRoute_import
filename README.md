# FortiGate 中国IP地址自动更新工具

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.6+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![FortiGate](https://img.shields.io/badge/FortiGate-v6.0+-red.svg)

基于苍狼IP库的飞塔防火墙中国三大运营商IP地址自动更新脚本

[功能特性](#功能特性) • [快速开始](#快速开始) • [部署方式](#部署方式) • [配置说明](#配置说明) • [故障排查](#故障排查)

</div>

---

## 📖 项目简介

本项目提供一个自动化脚本，用于定期从苍狼IP库获取最新的中国三大运营商（移动、联通、电信）及全国IP地址段，并自动更新到飞塔（FortiGate）防火墙中，实现IP地址的自动化管理。

### 应用场景

- 🌐 **国内加速**：将中国IP地址段单独管理，实现国内直连、国外代理
- 🔒 **访问控制**：基于运营商对流量进行精细化控制
- 📊 **流量分析**：区分不同运营商的流量统计
- 🚀 **路由优化**：根据运营商选择最优路由路径

### 数据源

使用 [苍狼IP库](https://ispip.clang.cn/) 提供的IP地址数据：
- 🔴 中国移动（CMCC）
- 🔵 中国联通（Unicom）
- 🟢 中国电信（Telecom）
- 🇨🇳 中国大陆全部IP（ALL-CN）

---

## ✨ 功能特性

### 核心功能

- ✅ **自动更新**：每天定时从苍狼IP库获取最新IP地址段
- ✅ **全量更新策略**：先删除旧地址，再创建新地址，确保数据准确
- ✅ **高速并发**：支持多线程并发处理，快速完成大量地址对象的创建和删除
- ✅ **智能备份**：每次更新前自动备份当前配置
- ✅ **详细日志**：完整记录每次更新的详细信息
- ✅ **自动分组**：自动维护4个地址组（移动、联通、电信、全国）
- ✅ **错误重试**：失败的操作自动重试，提高成功率

### 额外功能

- 📱 **企业微信通知**：更新完成后自动发送通知到企业微信群
- 🔄 **连接池管理**：优化API连接池，避免连接耗尽
- 🛡️ **引用处理**：智能处理地址组引用，确保删除成功
- 📊 **统计报告**：详细的创建/删除/失败统计

---

## 🚀 快速开始

### 系统要求

- Python 3.6+
- FortiGate 防火墙（v6.0+，支持REST API）
- Linux服务器（推荐 Ubuntu/CentOS）
- 网络连接（能访问 ispip.clang.cn 和防火墙管理地址）

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/xuepudong/Fortinet_ChinaRoute_import.git
cd fortigate-cn-ip-updater
```

#### 2. 安装依赖

```bash
pip3 install -r requirements.txt
```

#### 3. 配置脚本

编辑 `fortigate_cn_ip_updater.py`，修改配置部分：

```python
CONFIG = {
    # 飞塔防火墙配置
    'FW_HOST': '10.4.0.1',              # 防火墙IP地址
    'FW_PORT': 8443,                    # 管理端口
    'API_TOKEN': 'your_api_token_here', # API令牌
    'VDOM': 'root',                     # VDOM名称

    # 定时任务配置
    'UPDATE_TIME': '03:00',             # 每天更新时间

    # 企业微信通知（可选）
    'WECHAT_WEBHOOK': '',               # 企业微信机器人webhook

    # 并发配置
    'MAX_WORKERS': 20,                  # 并发线程数
}
```

#### 4. 测试运行

```bash
# 执行一次更新测试
python3 fortigate_cn_ip_updater.py --once
```

---

## 🔧 配置说明

### 获取 FortiGate API Token

1. 登录 FortiGate Web 管理界面
2. 进入 **System** > **Administrators**
3. 创建 **REST API Admin**：
   - 类型：REST API Admin
   - 用户名：api_user
   - 管理员权限：Super_Admin
   - 信任主机：运行脚本的服务器IP
4. 创建后会显示 API Token，**复制保存**（只显示一次）

### 配置企业微信通知

1. 打开企业微信群聊
2. 右上角 **...** > **群机器人** > **添加机器人**
3. 选择 **自定义机器人**
4. 填写机器人名称（如：FortiGate更新通知）
5. 复制 **Webhook 地址**
6. 将地址填入配置文件的 `WECHAT_WEBHOOK` 字段

### 地址对象命名规则

脚本创建的地址对象命名格式：`运营商_IP网段`

示例：
- `CMCC_1.2.3.0_24` - 移动：1.2.3.0/24
- `Unicom_10.0.0.0_8` - 联通：10.0.0.0/8
- `Telecom_192.168.1.0_24` - 电信：192.168.1.0/24
- `ALL-CN_172.16.0.0_12` - 全国：172.16.0.0/12

### 地址组名称

脚本会自动创建并维护4个地址组：
- `Group_CMCC` - 中国移动
- `Group_Unicom` - 中国联通
- `Group_Telecom` - 中国电信
- `Group_ALL-CN` - 中国大陆全部

---

## 📦 部署方式

### 方式二：Systemd 服务

**适用场景**：生产环境，需要开机自启和自动重启

#### 1. 创建服务文件

```bash
sudo nano /etc/systemd/system/fortigate-updater.service
```

内容：

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
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### 2. 部署脚本

```bash
# 创建目录
sudo mkdir -p /opt/fortigate-updater

# 复制文件
sudo cp fortigate_cn_ip_updater.py /opt/fortigate-updater/
sudo cp requirements.txt /opt/fortigate-updater/

# 安装依赖
cd /opt/fortigate-updater
sudo pip3 install -r requirements.txt
```

#### 3. 启动服务

```bash
# 重载配置
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable fortigate-updater

# 启动服务
sudo systemctl start fortigate-updater

# 查看状态
sudo systemctl status fortigate-updater
```

#### 4. 管理服务

```bash
# 查看日志
sudo journalctl -u fortigate-updater -f

# 重启服务
sudo systemctl restart fortigate-updater

# 停止服务
sudo systemctl stop fortigate-updater
```

---

### 方式三：Cron 定时任务

**适用场景**：简单部署，不需要脚本常驻

#### 1. 编辑 crontab

```bash
crontab -e
```

#### 2. 添加定时任务

```bash
# 每天凌晨3点执行
0 3 * * * cd /opt/fortigate-updater && /usr/bin/python3 fortigate_cn_ip_updater.py --once >> /var/log/fortigate-update.log 2>&1
```

#### 3. 验证配置

```bash
# 查看已配置的定时任务
crontab -l

# 手动测试
cd /opt/fortigate-updater
python3 fortigate_cn_ip_updater.py --once
```

---

### 方式一：Docker 部署（推荐）

**适用场景**：容器化部署，支持 amd64 / arm64 多架构

#### 使用预构建镜像

```bash
docker pull xuepudong/fortigate-cn-ip-updater:latest
```

#### 运行方式一：常驻定时模式（每天自动更新）

```bash
docker run -d --restart unless-stopped \
  --name fortigate-cn-ip-updater \
  -e FW_HOST=192.168.1.1 \
  -e FW_PORT=443 \
  -e API_TOKEN=your_api_token_here \
  -e VDOM=root \
  -e UPDATE_TIME=03:00 \
  -e WECHAT_WEBHOOK= \
  -v $(pwd)/backups:/app/backups \
  -v $(pwd)/logs:/app/logs \
  xuepudong/fortigate-cn-ip-updater:latest
```

#### 运行方式二：执行一次后退出（适合外部 cron 调度）

```bash
docker run --rm \
  -e FW_HOST=192.168.1.1 \
  -e API_TOKEN=your_api_token_here \
  -v $(pwd)/backups:/app/backups \
  -v $(pwd)/logs:/app/logs \
  xuepudong/fortigate-cn-ip-updater:latest \
  python -u fortigate_cn_ip_updater.py --once
```

#### 使用 Docker Compose

创建 `docker-compose.yml`：

```yaml
services:
  fortigate-updater:
    image: xuepudong/fortigate-cn-ip-updater:latest
    container_name: fortigate-cn-ip-updater
    restart: unless-stopped
    environment:
      - FW_HOST=192.168.1.1
      - FW_PORT=443
      - API_TOKEN=your_api_token_here
      - VDOM=root
      - UPDATE_TIME=03:00
      - WECHAT_WEBHOOK=
    volumes:
      - ./backups:/app/backups
      - ./logs:/app/logs
```

启动：

```bash
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

#### 自行构建镜像（多架构）

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t your-registry/fortigate-cn-ip-updater:latest \
  --push .
```

#### 环境变量说明

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `FW_HOST` | 是 | - | 防火墙 IP 地址 |
| `FW_PORT` | 否 | `443` | 防火墙管理端口 |
| `API_TOKEN` | 是 | - | FortiGate API Token |
| `VDOM` | 否 | `root` | VDOM 名称 |
| `UPDATE_TIME` | 否 | `03:00` | 每天定时更新时间 |
| `WECHAT_WEBHOOK` | 否 | - | 企业微信机器人 Webhook URL |

---

### 方式四：Nohup 后台运行

**适用场景**：临时运行，快速测试

```bash
# 启动
cd /opt/fortigate-updater
nohup python3 fortigate_cn_ip_updater.py --now > nohup.out 2>&1 &

# 查看日志
tail -f nohup.out

# 停止
pkill -f fortigate_cn_ip_updater

# 查看进程
ps aux | grep fortigate_cn_ip_updater
```

---

## 💻 命令行参数

脚本支持以下命令行参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| 无参数 | 启动定时任务，等待每天指定时间执行 | `python3 fortigate_cn_ip_updater.py` |
| `--now` | 启动时立即执行一次，然后继续定时任务 | `python3 fortigate_cn_ip_updater.py --now` |
| `--once` | 只执行一次更新后退出（适用于cron） | `python3 fortigate_cn_ip_updater.py --once` |
| `-h, --help` | 显示帮助信息 | `python3 fortigate_cn_ip_updater.py -h` |

### 使用示例

```bash
# 立即执行一次并查看输出
python3 fortigate_cn_ip_updater.py --once

# 后台运行定时任务，启动时执行一次
nohup python3 fortigate_cn_ip_updater.py --now > nohup.out 2>&1 &

# 启动定时任务，不立即执行
python3 fortigate_cn_ip_updater.py
```

---

## 📊 日志和监控

### 日志文件位置

```
fortigate-updater/
├── logs/
│   └── cn_ip_update_20260123.log    # 每天一个日志文件
├── backups/
│   └── backup_20260123_030000.json  # 每次更新前的备份
└── nohup.out                         # nohup运行的输出日志
```

### 日志示例

```
2026-01-23 03:00:00,123 [INFO] ================================================================================
2026-01-23 03:00:00,123 [INFO] 飞塔防火墙中国IP地址更新任务开始
2026-01-23 03:00:00,123 [INFO] ================================================================================
2026-01-23 03:00:00,456 [INFO] 正在备份当前配置...
2026-01-23 03:00:01,789 [INFO] 备份完成: backups/backup_20260123_030000.json
2026-01-23 03:00:01,790 [INFO] ============================================================
2026-01-23 03:00:01,790 [INFO] 开始更新 CMCC
2026-01-23 03:00:01,790 [INFO] ============================================================
2026-01-23 03:00:02,100 [INFO] 正在获取IP列表: https://ispip.clang.cn/cmcc.txt
2026-01-23 03:00:02,350 [INFO] 获取到 296 个IP段
2026-01-23 03:00:02,350 [INFO] 从地址组中移除 CMCC 地址引用...
2026-01-23 03:00:02,360 [INFO]   地址组 Group_CMCC 会变空，使用占位符 'all'
2026-01-23 03:00:02,370 [INFO]   更新地址组 Group_CMCC: 296 -> 1 成员
2026-01-23 03:00:03,500 [INFO] 正在删除 296 个旧的 CMCC 地址对象...
2026-01-23 03:00:05,800 [INFO] 删除完成: 296/296
2026-01-23 03:00:07,900 [INFO] 正在创建 296 个地址对象...
2026-01-23 03:00:10,200 [INFO]   已创建 100/296...
2026-01-23 03:00:12,500 [INFO]   已创建 200/296...
2026-01-23 03:00:14,800 [INFO] 创建完成: 成功 296, 失败 0
2026-01-23 03:00:14,900 [INFO] 地址组 Group_CMCC 已存在
2026-01-23 03:00:15,100 [INFO] 地址组 Group_CMCC 更新成功 (296 个成员)
2026-01-23 03:00:15,100 [INFO] CMCC 更新完成
```

### 查看日志

```bash
# 查看今天的详细日志
tail -f logs/cn_ip_update_$(date +%Y%m%d).log

# 查看 nohup 输出
tail -f nohup.out

# 查看 systemd 服务日志
sudo journalctl -u fortigate-updater -f

# 查看最近100行日志
tail -100 logs/cn_ip_update_$(date +%Y%m%d).log
```

### 监控脚本运行状态

```bash
# 检查进程是否运行
ps aux | grep fortigate_cn_ip_updater

# 检查最后一次更新时间
ls -lh logs/ | tail -1

# 查看备份文件
ls -lh backups/ | tail -5
```

---

## 🔍 故障排查

### 问题1：脚本无法启动

**症状**：运行脚本报错或无输出

**排查步骤**：

```bash
# 1. 检查Python版本（需要3.6+）
python3 --version

# 2. 检查依赖是否安装
pip3 list | grep -E "requests|urllib3|schedule"

# 3. 重新安装依赖
pip3 install -r requirements.txt --upgrade

# 4. 检查脚本语法
python3 -m py_compile fortigate_cn_ip_updater.py
```

---

### 问题2：无法连接防火墙

**症状**：日志显示连接超时或拒绝

**排查步骤**：

```bash
# 1. 检查网络连通性
ping 10.4.0.1

# 2. 检查端口是否开放
telnet 10.4.0.1 8443

# 3. 测试HTTPS连接
curl -k https://10.4.0.1:8443

# 4. 检查防火墙配置
# - 确认API访问已启用
# - 确认信任主机列表包含运行脚本的服务器IP
# - 确认API Token有效且权限足够
```

---

### 问题3：地址创建失败

**症状**：日志显示 "创建完成: 成功 0, 失败 296"

**可能原因**：
- ❌ 地址对象已存在
- ❌ 地址对象被引用无法删除
- ❌ API Token权限不足
- ❌ 防火墙存储空间不足

**解决方法**：

```bash
# 1. 查看详细错误信息
tail -50 logs/cn_ip_update_$(date +%Y%m%d).log | grep -A 5 "失败"

# 2. 手动清理旧地址对象
# 登录防火墙 Web 界面，进入 Policy & Objects > Addresses
# 搜索并删除所有 CMCC_、Unicom_、Telecom_、ALL-CN_ 前缀的地址

# 3. 检查地址组引用
# 进入 Policy & Objects > Address Groups
# 查看 Group_CMCC 等地址组，确保可以修改

# 4. 重新运行脚本
python3 fortigate_cn_ip_updater.py --once
```

---

### 问题4：定时任务不执行

**症状**：脚本在运行，但凌晨3点没有执行更新

**排查步骤**：

```bash
# 1. 检查进程是否运行
ps aux | grep fortigate_cn_ip_updater

# 2. 检查服务器时间是否正确
date

# 3. 检查时区设置
timedatectl

# 4. 查看日志确认定时任务状态
tail -f nohup.out

# 5. 测试立即执行
python3 fortigate_cn_ip_updater.py --once
```

---

### 问题5：无法获取IP列表

**症状**：日志显示 "获取到 0 个IP段"

**排查步骤**：

```bash
# 1. 检查网络连接
curl -I https://ispip.clang.cn/cmcc.txt

# 2. 手动下载测试
wget https://ispip.clang.cn/cmcc.txt -O test.txt
cat test.txt | wc -l

# 3. 检查DNS解析
nslookup ispip.clang.cn

# 4. 检查防火墙/代理设置
# 确保服务器可以访问外网
```

---

### 问题6：企业微信通知未收到

**症状**：更新完成但没有收到企业微信通知

**排查步骤**：

```bash
# 1. 检查配置是否填写
grep WECHAT_WEBHOOK fortigate_cn_ip_updater.py

# 2. 测试 Webhook 连接
curl -X POST 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY' \
   -H 'Content-Type: application/json' \
   -d '{"msgtype":"text","text":{"content":"测试消息"}}'

# 3. 查看日志中的通知发送状态
grep "企业微信" logs/cn_ip_update_$(date +%Y%m%d).log
```

---

## 🔒 安全建议

### 1. API Token 安全

```bash
# 不要将 API Token 硬编码在脚本中
# 推荐使用环境变量

# 设置环境变量
export FG_API_TOKEN="your_api_token_here"

# 修改脚本读取环境变量
import os
CONFIG = {
    'API_TOKEN': os.getenv('FG_API_TOKEN', ''),
}
```

### 2. 文件权限

```bash
# 设置脚本只有 root 可读
sudo chmod 600 fortigate_cn_ip_updater.py

# 设置日志目录权限
sudo chmod 700 logs backups
```

### 3. 网络隔离

- 🔒 将运行脚本的服务器IP加入防火墙信任主机列表
- 🔒 使用防火墙策略限制API访问来源
- 🔒 启用HTTPS和证书验证（生产环境）

### 4. 日志脱敏

```bash
# 定期清理旧日志（保留最近30天）
find logs/ -name "*.log" -mtime +30 -delete
find backups/ -name "*.json" -mtime +30 -delete
```

---

## 📈 性能优化

### 调整并发线程数

根据防火墙性能和网络情况调整：

```python
CONFIG = {
    'MAX_WORKERS': 20,  # 默认20个并发
}
```

- 🔹 **低配防火墙**：10-15 个线程
- 🔹 **中配防火墙**：20-30 个线程
- 🔹 **高配防火墙**：30-50 个线程

### 优化更新时间

选择业务低峰期执行更新：

```python
CONFIG = {
    'UPDATE_TIME': '03:00',  # 凌晨3点
}
```

### 监控资源使用

```bash
# 查看脚本内存占用
ps aux | grep fortigate_cn_ip_updater

# 查看网络连接数
netstat -an | grep 8443 | wc -l

# 查看磁盘使用
du -sh logs/ backups/
```

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/xuepudong/Fortinet_ChinaRoute_import.git
cd fortigate-cn-ip-updater

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行测试
python3 fortigate_cn_ip_updater.py --once
```

### 提交规范

- 🐛 **Bug修复**：`fix: 修复xxx问题`
- ✨ **新功能**：`feat: 添加xxx功能`
- 📝 **文档**：`docs: 更新xxx文档`
- 🔧 **配置**：`chore: 修改xxx配置`

---

## 📝 更新日志

### v1.0.0 (2026-01-23)

- ✅ 初始版本发布
- ✅ 支持四大运营商IP自动更新
- ✅ 支持企业微信通知
- ✅ 支持多种部署方式
- ✅ 完整的日志和备份机制

---

## ⚠️ 免责声明

本工具仅供学习和研究使用，使用本工具产生的任何后果由使用者自行承担。

- ⚠️ 请在测试环境充分测试后再用于生产环境
- ⚠️ 建议在业务低峰期执行更新
- ⚠️ 更新前请确保有防火墙配置备份
- ⚠️ 大量地址对象可能影响防火墙性能

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- [苍狼IP库](https://ispip.clang.cn/) - 提供IP地址数据
- [FortiGate REST API](https://docs.fortinet.com/document/fortigate/7.4.0/administration-guide/399023/rest-api) - API文档
- 所有贡献者和使用者

---

## 📧 联系方式

- **Issues**: [GitHub Issues](https://github.com/xuepudong/Fortinet_ChinaRoute_import/issues)
- **Email**: pudong.xue@bjyy.info
- **企业微信**: 可添加机器人到您的企业微信群

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐️ Star 支持一下！**

Made with ❤️ by [Beijing Yiyuan Information Technology Co., Ltd.](https://www.bjyy.info)

</div>
