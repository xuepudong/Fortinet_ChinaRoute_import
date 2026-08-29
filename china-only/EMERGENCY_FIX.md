# 紧急性能优化方案

## 🚨 问题现状

**症状**：20 分钟只处理了 11 个批次（共约 27 批次）
**预计总耗时**：约 50 分钟才能完成一次更新
**根本原因**：你的 FortiGate 型号处理大地址组的能力极其有限

---

## 💊 立即优化方案

### 方案 1：大幅降低批次大小（推荐，立即生效）

当前批次大小 300 条对你的 FortiGate 来说仍然太大。

#### 修改步骤：

```bash
# 1. 停止当前运行的容器
docker compose down

# 2. 编辑脚本
nano china-only/fortigate_cn_ip_updater.py

# 3. 找到第 510 行，修改批次大小
# 从：batch_size = 300
# 改为：batch_size = 50   # 极大降低批次大小

# 4. 同时修改第 540 行的超时时间，进一步增加
# 从：timeout = 60 + (batch_num * 10)
# 改为：timeout = 120 + (batch_num * 20)  # 翻倍超时时间

# 5. 重新构建并启动
docker compose build
docker compose up -d
```

**效果预测**：
- 批次数：27 批 → 162 批
- 单批处理时间：2 分钟 → 20-30 秒
- 总耗时：50 分钟 → 15-20 分钟

---

### 方案 2：分步更新策略（治本方案）

如果方案 1 仍然慢，考虑将 8000+ 条记录拆分成多个小地址组。

#### 实施步骤：

创建新脚本 `fortigate_cn_ip_updater_split.py`，将一个大组拆成 4 个小组：
- `Group_ALL-CN-Part1`（1-2000）
- `Group_ALL-CN-Part2`（2001-4000）
- `Group_ALL-CN-Part3`（4001-6000）
- `Group_ALL-CN-Part4`（6001-8000+）

**优点**：
- 每个小组只有 2000 条记录
- 更新速度快 10 倍以上
- 单个小组更新失败不影响其他组

**缺点**：
- 防火墙策略需要引用 4 个地址组（OR 关系）
- 需要修改现有策略

---

### 方案 3：禁用重试和批次间延迟（临时加速）

**仅用于测试，不推荐生产环境！**

```python
# 第 467 行，注释掉批次间延迟
# if i + batch_size < len(members):
#     time.sleep(2)

# 第 536-560 行，注释掉重试逻辑
max_retries = 1  # 从 2 改为 1
```

**风险**：失败率会增加，但速度会快 30%

---

## 🎯 立即执行（最快方案）

```bash
# 停止容器
cd /Users/xuepudong/kaifa/Fortinet_ChinaRoute_import/china-only
docker compose down

# 快速修改
sed -i.bak 's/batch_size = 300/batch_size = 50/g' fortigate_cn_ip_updater.py
sed -i.bak 's/timeout = 60 + (batch_num \* 10)/timeout = 120 + (batch_num * 20)/g' fortigate_cn_ip_updater.py

# 重新启动
docker compose build
docker compose up -d

# 查看日志
docker compose logs -f
```

---

## 📊 根据 FortiGate 型号选择批次大小

| FortiGate 型号 | 推荐 batch_size | 预计总耗时 |
|---------------|-----------------|-----------|
| 40F, 60F      | 50              | 15-20 分钟 |
| 80F, 100F     | 100             | 10-15 分钟 |
| 200F          | 200             | 5-10 分钟  |
| 400F+         | 300             | 3-5 分钟   |

**你的情况**：建议从 **batch_size = 50** 开始测试

---

## 🔍 诊断你的 FortiGate 型号

```bash
# 查看 FortiGate 型号信息
curl -k -H "Authorization: Bearer YOUR_API_TOKEN" \
  https://10.5.0.1:443/api/v2/monitor/system/status

# 查看系统资源使用
curl -k -H "Authorization: Bearer YOUR_API_TOKEN" \
  https://10.5.0.1:443/api/v2/monitor/system/resource/usage
```

---

## ⚡ 终极方案：使用增量更新而非全量更新

如果每次都需要 50 分钟，建议改为**增量更新策略**：
1. 首次全量更新（接受 50 分钟）
2. 后续只更新变化的 IP 段（通常只有几十条）
3. 每周或每月做一次全量更新

这需要修改脚本逻辑，计算差异而不是全部删除再创建。

---

## 💡 当前建议

**立即执行**：将 `batch_size` 改为 **50**，超时翻倍

如果仍然很慢，考虑：
1. 升级 FortiGate 固件到最新版本
2. 检查 FortiGate 是否有其他高负载任务
3. 考虑方案 2（拆分成多个小地址组）
