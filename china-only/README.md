# FortiGate 中国IP自动更新 · ALL-CN 精简版（Docker）

只维护一个地址组 `Group_ALL-CN`，包含中国大陆全部 IP 段（数据源：苍狼IP库 `all_cn.txt`）。
**不会**创建移动 / 联通 / 电信的独立地址组。

支持 `linux/amd64` 与 `linux/arm64`，可直接构建并推送到 Docker Hub。

## 快速开始（使用已发布镜像）

改 `docker-compose.yml` 里的 `image`、`FW_HOST`、`API_TOKEN`，然后：

```bash
docker compose up -d
docker compose logs -f
```

启动时立即执行一次全量更新，之后每天 `UPDATE_TIME`（默认 03:00，容器时区 Asia/Shanghai）自动更新。

或不用 compose：

```bash
docker run -d --name fortigate-allcn-updater --restart unless-stopped \
  -e FW_HOST=192.168.1.1 \
  -e API_TOKEN=your_api_token_here \
  -e UPDATE_TIME=03:00 \
  -e TZ=Asia/Shanghai \
  -v "$PWD/logs:/app/logs" -v "$PWD/backups:/app/backups" \
  youruser/fortigate-cn-updater:latest --now
```

## 构建并推送到 Docker Hub

```bash
docker login
./build.sh youruser/fortigate-cn-updater v1.0.0
```

`build.sh` 会自动创建 `docker-container` driver 的 buildx builder，构建 `linux/amd64,linux/arm64` 两个架构并推送同一个 manifest list，同时给非 `latest` 的标签额外打上 `latest`。

只想验证能编译、不推送：

```bash
PUSH=0 ./build.sh youruser/fortigate-cn-updater
```

改架构组合：`PLATFORMS=linux/amd64 ./build.sh ...`

手动等价命令：

```bash
docker buildx create --name b --driver docker-container --bootstrap
docker buildx build --builder b --platform linux/amd64,linux/arm64 \
  -t youruser/fortigate-cn-updater:latest --push .
docker buildx imagetools inspect youruser/fortigate-cn-updater:latest
```

多平台镜像无法 `--load` 进本地 Docker，本地调试请指定单一架构：
`docker buildx build --platform linux/arm64 --load -t test .`

### GitHub Actions 自动发布

仓库根目录已有 `.github/workflows/docker-publish.yml`：推 `v*` tag 即构建双架构并推送。需在仓库 Secrets 配置 `DOCKERHUB_USERNAME` 和 `DOCKERHUB_TOKEN`（Docker Hub Access Token）。

```bash
git tag v1.0.0 && git push origin v1.0.0
```


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

# 只做定时，不在启动时立即执行：把 compose 里的 command 一行删掉即可
```

`--now` 启动即更新 + 常驻定时；`--once` 更新一次后退出；不带参数则纯定时常驻。

## 更新流程

1. 备份当前 `ALL-CN_*` 地址对象与 `Group_ALL-CN` 到 `./backups/`
2. 从所有地址组中摘除 `ALL-CN_*` 引用（若地址组会变空，临时填入内置对象 `all`）
3. 删除旧的 `ALL-CN_*` 地址对象
4. 拉取最新 IP 段，批量创建地址对象（命名 `ALL-CN_1.2.3.0_24`）
   - 支持超时自动重试
   - 失败的地址会在5秒后降低并发重试一次
   - 只有成功创建的地址才会加入地址组
5. 写回 `Group_ALL-CN` 成员（按 1000 条分批 PUT，仅包含成功创建的地址）

**资源不足处理**：当 FortiGate 资源紧张导致创建失败时，脚本会自动：
- 检测超时和资源不足错误并重试
- 在首次批量创建后等待5秒，以更低的并发（原并发的一半，最少5）重试所有失败的地址
- 确保只将成功创建的地址加入地址组，避免引用不存在的地址对象

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

## 故障排查

### 连接超时

日志出现 `ConnectTimeoutError ... Connection to <FW_HOST> timed out` 表示 TCP 都没握手成功，与认证、证书无关。先分别测宿主机和容器：

```bash
# 宿主机
curl -k -m 10 -I https://<FW_HOST>:<FW_PORT>

# 容器内（镜像未装 curl，用 python）
docker exec fortigate-allcn-updater \
  python -c "import socket;socket.create_connection(('<FW_HOST>',<FW_PORT>),5);print('ok')"
```

| 现象 | 原因与处理 |
|---|---|
| 宿主机通、容器不通 | 宿主机防火墙未放通容器网段转发（iStoreOS/OpenWrt 默认不允许 docker zone → lan zone）。最简单的处理是在 compose 中启用 `network_mode: host` |
| 都不通 | FortiGate 侧：`FW_PORT` 不对（常见 8443），或该接口 `allowaccess` 未包含 `https` |
| 都通但 API 报错 | API 用户 trusthost 未放通宿主机 IP（容器经 bridge 出站会 SNAT 成宿主机 IP） |

启用 host 网络（编辑 `docker-compose.yml`，取消 `network_mode: host` 注释）后重建容器：

```bash
docker compose up -d --force-recreate
```

### 读取超时 (ReadTimeoutError)

日志频繁出现 `ReadTimeoutError: Read timed out. (read timeout=30)` 有两种情况：

#### 1. 创建地址对象时超时
FortiGate 资源不足，处理请求过慢。

**解决方案**：
- 降低并发数：设置 `MAX_WORKERS=5` 或 `MAX_WORKERS=10`（默认 20）
- 脚本已内置重试机制，会自动重试失败的地址
- 在 FortiGate 低峰时段执行更新

```yaml
# docker-compose.yml 中添加
environment:
  - MAX_WORKERS=5
```

#### 2. 更新地址组时超时 (更常见)
当地址组包含 8000+ 条记录时，FortiGate 处理大 JSON 负载需要很长时间，特别是后面几批更新时。

**根本原因**：
- 每批更新需要先 GET 当前所有成员（8000+ 条），再 PUT 追加新成员
- 随着地址组变大，FortiGate 的验证和索引时间呈指数级增长
- 这是 FortiGate API 的性能瓶颈，与你的机器性能无关

**脚本已优化**：
- 批次大小从 1000 降至 300
- 超时时间动态调整（第1批60秒，后续递增到120秒+）
- 每批自动重试最多2次
- 批次间增加2秒延迟

如果仍然超时，说明你的 FortiGate 型号处理能力有限，可以：
1. 进一步降低批次大小（修改脚本第 510 行 `batch_size = 300` 改为 `100`）
2. 选择业务最低峰时段执行
3. 考虑升级 FortiGate 固件或硬件

## 注意事项

- 全量 ALL-CN 约 8000+ 条地址对象，首次执行可能耗时数分钟，且会占用 FortiGate 地址对象配额，低端型号请先确认上限。
- 更新过程中 `Group_ALL-CN` 会短暂变空并被填入 `all`（等价于匹配全部地址）。**如果该地址组已被安全策略引用，这个窗口期内策略行为会变成匹配任意地址**，建议在业务低峰执行，或先在测试设备验证。
- 从完整版（含 CMCC/Unicom/Telecom 分组）迁移过来时，本版本不会清理已存在的 `CMCC_*`、`Unicom_*`、`Telecom_*` 地址对象和对应地址组，需要手动删除。
- 脚本对 FortiGate 使用 `verify=False` 跳过证书校验（自签名证书场景），仅适用于可信内网链路。
- 容器以 root 运行，因为 `./logs`、`./backups` 是宿主机 bind mount，非 root 用户常因属主不符而写入失败。
