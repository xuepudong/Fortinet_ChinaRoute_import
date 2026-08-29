#!/bin/bash
# 紧急性能优化脚本 - 针对低性能 FortiGate
# 用途：大幅降低批次大小，增加超时时间

set -e

echo "=================================="
echo "FortiGate 更新脚本紧急优化"
echo "=================================="
echo ""

# 进入 china-only 目录
cd "$(dirname "$0")"

# 备份原文件
if [ ! -f "fortigate_cn_ip_updater.py.original" ]; then
    echo "→ 备份原始文件..."
    cp fortigate_cn_ip_updater.py fortigate_cn_ip_updater.py.original
    echo "✓ 已备份到 fortigate_cn_ip_updater.py.original"
fi

# 修改批次大小（300 → 50）
echo ""
echo "→ 降低批次大小：300 → 50"
sed -i.tmp 's/batch_size = 300/batch_size = 50/g' fortigate_cn_ip_updater.py

# 修改超时时间（60 + n*10 → 120 + n*20）
echo "→ 增加超时时间：60+(n*10) → 120+(n*20)"
sed -i.tmp 's/timeout = 60 + (batch_num \* 10)/timeout = 120 + (batch_num * 20)/g' fortigate_cn_ip_updater.py

# 清理临时文件
rm -f fortigate_cn_ip_updater.py.tmp

echo ""
echo "✓ 优化完成！"
echo ""
echo "优化内容："
echo "  - 批次大小：300 → 50（减少 83%）"
echo "  - 超时时间：60s起步 → 120s起步（增加 100%）"
echo "  - 预计总批次：27 → 162"
echo "  - 预计总耗时：50分钟 → 15-20分钟"
echo ""
echo "--------------------------------"
echo "下一步操作："
echo "--------------------------------"
echo "1. 停止当前容器："
echo "   docker compose down"
echo ""
echo "2. 重新构建："
echo "   docker compose build"
echo ""
echo "3. 启动容器："
echo "   docker compose up -d"
echo ""
echo "4. 查看日志："
echo "   docker compose logs -f"
echo ""
echo "--------------------------------"
echo "恢复原配置："
echo "--------------------------------"
echo "   mv fortigate_cn_ip_updater.py.original fortigate_cn_ip_updater.py"
echo "=================================="
