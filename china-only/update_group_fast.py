#!/usr/bin/env python3
"""
紧急修复：一次性更新地址组，避免反复 GET+PUT
"""

def update_group_members_fast(self, group_name, member_names):
    """一次性更新地址组成员（避免分批导致的越来越慢）"""
    url = f"{self.base_url}/cmdb/firewall/addrgrp/{group_name}"
    params = {'vdom': self.vdom}

    # 将成员名称转换为API需要的格式
    members = [{'name': name} for name in member_names]

    self.logger.info(f"开始更新地址组 {group_name}，共 {len(member_names)} 个成员")
    self.logger.info(f"⚠️ 使用一次性更新模式（不分批，可能需要 5-10 分钟）")

    # 计算合理的超时时间：每1000条记录给30秒
    timeout = max(180, (len(members) // 1000 + 1) * 30)
    self.logger.info(f"  设置超时时间：{timeout} 秒")

    # 一次性替换所有成员
    data = {'member': members}

    max_retries = 3
    for retry in range(max_retries):
        try:
            self.logger.info(f"  正在提交 {len(members)} 个成员...")
            response = self.session.put(url, params=params, json=data, verify=False, timeout=timeout)

            if response.status_code == 200:
                self.logger.info(f"✓ 地址组 {group_name} 更新成功 ({len(member_names)} 个成员)")
                return True
            else:
                error_msg = response.json() if response.status_code != 200 else 'Unknown error'
                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 60  # 第1次等60秒，第2次等120秒
                    self.logger.warning(f"  更新失败 (HTTP {response.status_code})，等待 {wait_time} 秒后重试...")
                    self.logger.warning(f"  错误详情: {error_msg}")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"  更新失败，已重试 {max_retries} 次")
                    self.logger.error(f"  错误详情: {error_msg}")
                    return False

        except Exception as e:
            if 'timeout' in str(e).lower() or 'timed out' in str(e).lower():
                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 60
                    self.logger.warning(f"  超时，等待 {wait_time} 秒后重试（第 {retry + 1}/{max_retries} 次）...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"  超时失败，已重试 {max_retries} 次: {e}")
                    return False
            else:
                self.logger.error(f"  异常: {e}")
                return False

    return False


# 使用说明：
# 1. 将此方法替换 fortigate_cn_ip_updater.py 中的 update_group_members 方法
# 2. 优点：避免分批导致的越来越慢
# 3. 缺点：一次性提交 8000+ 条，如果失败则全部失败
# 4. 适用于：地址创建成功率高的情况
