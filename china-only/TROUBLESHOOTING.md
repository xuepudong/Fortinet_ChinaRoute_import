# 故障排查指南

## ReadTimeoutError 超时问题深度分析

### 症状
即使 CPU 是 i9-10980XE，`MAX_WORKERS=5` 时仍频繁出现：
```
[WARNING] Retrying (Retry(total=2, ...)) after connection broken by 
'ReadTimeoutError("HTTPSConnectionPool(host='10.5.0.1', port=443): 
Read timed out. (read timeout=30)")': /api/v2/cmdb/firewall/addrgrp/Group_ALL-CN?vdom=root
```

### 根本原因

**这不是你机器的性能问题，而是 FortiGate API 的设计瓶颈！**

当更新包含 8000+ 条记录的地址组时：

1. **每批更新的实际操作**：
   - 先 GET `/api/v2/cmdb/firewall/addrgrp/Group_ALL-CN`（返回已有的 7000+ 条记录）
   - 再 PUT 新的 JSON（原有 7000+ 条 + 新增 300 条 = 7300+ 条）
   - FortiGate 需要：解析 JSON → 验证每个成员 → 重建索引 → 写入配置

2. **为什么越到后面越慢**：
   - 第 1 批：PUT 300 条，FortiGate 处理 300 条
   - 第 5 批：PUT 1500 条，FortiGate 处理 1500 条
   - 第 27 批：PUT 8100 条，FortiGate 处理 8100 条（超时风险极高）

3. **时间复杂度**：
   - 理论：O(n²)，n 是地址组总成员数
   - 实际：随着地址组变大，FortiGate 的内部验证和索引时间呈**指数级增长**

### v1.1.0 的优化

#### 已实施的改进
```python
# 批次大小：1000 → 300
batch_size = 300

# 动态超时：固定30秒 → 60-120+秒
timeout = 60 + (batch_num * 10)  # 第1批60s，第27批330s

# 超时重试：无 → 每批最多重试2次

# 批次间延迟：无 → 2秒缓冲
time.sleep(2)
```

#### 预期效果
- 减少单批 JSON 大小，降低 FortiGate 解析压力
- 给后期批次更长的处理时间
- 失败后自动重试
- 批次间让 FortiGate "喘口气"

### 如果仍然超时

#### 方案 1：进一步降低批次大小
编辑 `fortigate_cn_ip_updater.py` 第 510 行：
```python
batch_size = 100  # 从 300 改为 100
```

影响：
- 更新时间更长（批次数从 27 增加到 81）
- 但每批成功率更高

#### 方案 2：增加超时倍数
编辑第 540 行：
```python
timeout = 90 + (batch_num * 15)  # 从 60+(n*10) 改为 90+(n*15)
```

#### 方案 3：业务低峰执行
```yaml
# docker-compose.yml
environment:
  - UPDATE_TIME=04:00  # 凌晨4点，FortiGate 流量最低
```

#### 方案 4：检查 FortiGate 固件
某些老版本固件在处理大地址组时效率极低，建议升级到最新稳定版。

### 为什么不是机器性能问题

1. **瓶颈在 FortiGate**：
   - 你的 Docker 主机只负责发送 HTTP 请求
   - 真正的计算（解析、验证、索引）都在 FortiGate 上

2. **网络不是瓶颈**：
   - 8000 条记录的 JSON 约 200-300KB
   - 局域网传输时间 < 0.1 秒

3. **并发不是解决方案**：
   - 地址组更新是串行操作（必须先 GET 再 PUT）
   - 降低 `MAX_WORKERS` 只影响地址对象创建，不影响地址组更新

### FortiGate 型号建议

| 型号档次 | 推荐地址组规模 | 更新 8000+ 条预期 |
|---------|--------------|-----------------|
| 入门级 (40F, 60F) | < 3000 | 可能超时，建议 batch_size=100 |
| 中端 (100F, 200F) | < 6000 | 偶尔超时，batch_size=300 可用 |
| 高端 (400F+, VM02+) | 8000+ | 基本无压力 |

### 终极方案：分组策略

如果超时问题无法解决，考虑拆分为多个小地址组：
- `Group_CN_Part1`（1-2000）
- `Group_CN_Part2`（2001-4000）
- ...

然后在策略中引用多个地址组（OR 关系）。
