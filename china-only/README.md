# FortiGate 中国IP自动更新 · ALL-CN 精简版（Docker）

只维护一个地址组 `Group_ALL-CN`，包含中国大陆全部 IP 段（数据源：苍狼IP库 `all_cn.txt`）。
**不会**创建移动 / 联通 / 电信的独立地址组。

## 快速开始

改 `docker-compose.yml` 里的 `FW_HOST` 和 `API_TOKEN` 两行，然后：

```bash
docker compose up -d --build
docker compose logs -f
```

启动时立即执行一次全量更新，之后每天 `UPDATE_TIME`（默认 03:00，容器时区 Asia/Shanghai）自动更新。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `FW_HOST` | – | FortiGate 管理地址（必填） |
| `FW_PORT` | `443` | HTTPS 管理端口 |
| `API_TOKEN` | – | REST API Token（必填） |
| `VDOM` | `root` | VDOM 名称 |
| `UPDATE_TIME` | `03:00` | 每天更新时间（24小时制） |
| `GROUP_NAME` | `Group_ALL-CN` | 要维护的地址组名 |
| `IP_SOURCE_URL` | `https://ispip.clang.cn/all_cn.txt` | IP 数据源（一般不用改） |
| `MAX_WORKERS` | `20` | 并发线程数，API 报错可降到 5–10 |
| `WECHAT_WEBHOOK` | 空 | 企业微信机器人通知（可选） |
| `TZ` | `Asia/Shanghai` | 容器时区，影响定时时间 |

## 运行模式

```bash
# 只跑一次就退出（适合宿主机 cron 调度）
docker compose run --rm fortigate-cn-updater --once

# 只做定时，不在启动时立即执行
docker compose run -d fortigate-cn-updater
```

`--now` 启动即更新 + 常驻定时；`--once` 更新一次后退出；不带参数则纯定时常驻。

## 更新流程

1. 备份当前 `ALL-CN_*` 地址对象与 `Group_ALL-CN` 到 `./backups/`
2. 从所有地址组中摘除 `ALL-CN_*` 引用（若地址组会变空，临时填入内置对象 `all`）
3. 删除旧的 `ALL-CN_*` 地址对象
4. 拉取最新 IP 段，创建地址对象（命名 `ALL-CN_1.2.3.0_24`）
5. 写回 `Group_ALL-CN` 成员（按 1000 条分批 PUT）

数据目录挂载在宿主机：`./logs`（日志）、`./backups`（配置备份）。

## FortiGate 侧准备

创建 REST API 管理员并授予 `Firewall Objects` 读写权限，把源 IP 限制到运行容器的主机：

```
config system api-user
    edit "ipupdater"
        set api-key <TOKEN>
        set accprofile "prof_admin"
        set vdom "root"
        config trusthost
            edit 1
                set ipv4-trusthost <docker-host-ip> 255.255.255.255
            next
        end
    next
end
```

Token 直接写在 `docker-compose.yml` 里，因此不要把改过的 compose 文件提交到公开仓库。

## 注意事项

- 全量 ALL-CN 约 8000+ 条地址对象，首次执行可能耗时数分钟，且会占用 FortiGate 地址对象配额，低端型号请先确认上限。
- 更新过程中 `Group_ALL-CN` 会短暂变空并被填入 `all`（等价于匹配全部地址）。**如果该地址组已被安全策略引用，这个窗口期内策略行为会变成匹配任意地址**，建议在业务低峰执行，或先在测试设备验证。
- 从完整版（含 CMCC/Unicom/Telecom 分组）迁移过来时，本版本不会清理已存在的 `CMCC_*`、`Unicom_*`、`Telecom_*` 地址对象和对应地址组，需要手动删除。
- 脚本对 FortiGate 使用 `verify=False` 跳过证书校验（自签名证书场景），仅适用于可信内网链路。
