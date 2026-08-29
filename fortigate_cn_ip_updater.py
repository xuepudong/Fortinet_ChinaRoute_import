#!/usr/bin/env python3
"""
飞塔防火墙中国IP地址自动更新脚本
基于苍狼IP库，每天自动更新中国三大运营商的IP地址段
"""

import os
import requests
import urllib3
import json
import time
import schedule
import sys
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from pathlib import Path

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== 配置区域 ====================
CONFIG = {
    # 飞塔防火墙配置
    'FW_HOST': 'your_foritgate_ip_address',
    'FW_PORT': 443,
    'API_TOKEN': 'your_api_token_here',  # 建议使用环境变量
    'VDOM': 'root',

    # IP数据源配置
    'IP_SOURCES': {
        'CMCC': 'https://ispip.clang.cn/cmcc.txt',
        'Unicom': 'https://ispip.clang.cn/unicom_cnc.txt',
        'Telecom': 'https://ispip.clang.cn/chinatelecom.txt',
        'ALL-CN': 'https://ispip.clang.cn/all_cn.txt'
    },

    # 地址组名称配置
    'GROUPS': {
        'CMCC': 'Group_CMCC',
        'Unicom': 'Group_Unicom',
        'Telecom': 'Group_Telecom',
        'ALL-CN': 'Group_ALL-CN'
    },

    # 定时任务配置
    'UPDATE_TIME': '03:00',  # 每天凌晨3点

    # 企业微信通知配置（可选）
    'WECHAT_WEBHOOK': 'your_qiyewechat_webhook',  # 填入企业微信机器人webhook URL

    # 备份和日志配置
    'BACKUP_DIR': './backups',
    'LOG_DIR': './logs',

    # 并发配置
    'MAX_WORKERS': 20,
}
# ================================================

# 环境变量覆盖配置
if os.environ.get('FW_HOST'):
    CONFIG['FW_HOST'] = os.environ['FW_HOST']
if os.environ.get('FW_PORT'):
    CONFIG['FW_PORT'] = int(os.environ['FW_PORT'])
if os.environ.get('API_TOKEN'):
    CONFIG['API_TOKEN'] = os.environ['API_TOKEN']
if os.environ.get('VDOM'):
    CONFIG['VDOM'] = os.environ['VDOM']
if os.environ.get('WECHAT_WEBHOOK'):
    CONFIG['WECHAT_WEBHOOK'] = os.environ['WECHAT_WEBHOOK']
if os.environ.get('UPDATE_TIME'):
    CONFIG['UPDATE_TIME'] = os.environ['UPDATE_TIME']


class Logger:
    """日志管理器"""
    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # 配置日志
        log_file = self.log_dir / f"cn_ip_update_{datetime.now().strftime('%Y%m%d')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(msg)

    def warning(self, msg):
        self.logger.warning(msg)


class WeChatNotifier:
    """企业微信通知"""
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

    def send(self, title, content):
        """发送企业微信通知"""
        if not self.enabled:
            return

        try:
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {title}\n{content}"
                }
            }
            response = requests.post(self.webhook_url, json=data, timeout=10)
            if response.status_code == 200:
                logging.info("企业微信通知发送成功")
            else:
                logging.error(f"企业微信通知发送失败: {response.status_code}")
        except Exception as e:
            logging.error(f"企业微信通知异常: {e}")


class FortiGateIPUpdater:
    """飞塔防火墙IP更新器"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.host = config['FW_HOST']
        self.port = config['FW_PORT']
        self.vdom = config['VDOM']
        self.base_url = f"https://{self.host}:{self.port}/api/v2"

        # 配置Session和连接池
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {config["API_TOKEN"]}'})

        # 增加连接池大小，解决并发连接警告
        adapter = HTTPAdapter(
            pool_connections=config['MAX_WORKERS'],
            pool_maxsize=config['MAX_WORKERS'] * 2,
            max_retries=Retry(total=3, backoff_factor=0.3)
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        # 初始化通知器
        self.notifier = WeChatNotifier(config.get('WECHAT_WEBHOOK', ''))

        # 备份目录
        self.backup_dir = Path(config['BACKUP_DIR'])
        self.backup_dir.mkdir(exist_ok=True)

    def fetch_ip_list(self, url):
        """从URL获取IP列表"""
        try:
            self.logger.info(f"正在获取IP列表: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # 解析IP列表（每行一个IP段）
                ips = [line.strip() for line in response.text.strip().split('\n')
                       if line.strip() and not line.startswith('#')]
                self.logger.info(f"获取到 {len(ips)} 个IP段")
                return ips
            else:
                self.logger.error(f"获取IP列表失败: HTTP {response.status_code}")
                return []
        except Exception as e:
            self.logger.error(f"获取IP列表异常: {e}")
            return []

    def backup_current_config(self):
        """备份当前配置"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f"backup_{timestamp}.json"

            self.logger.info("正在备份当前配置...")

            # 获取所有地址对象
            url = f"{self.base_url}/cmdb/firewall/address"
            params = {'vdom': self.vdom}
            response = self.session.get(url, params=params, verify=False, timeout=30)

            backup_data = {
                'timestamp': timestamp,
                'addresses': [],
                'groups': []
            }

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    # 只备份相关的地址对象
                    all_addresses = result.get('results', [])
                    prefixes = list(self.config['GROUPS'].keys())
                    backup_data['addresses'] = [
                        addr for addr in all_addresses
                        if any(addr['name'].startswith(f"{p}_") for p in prefixes)
                    ]

            # 获取地址组
            url = f"{self.base_url}/cmdb/firewall/addrgrp"
            response = self.session.get(url, params=params, verify=False, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    all_groups = result.get('results', [])
                    group_names = list(self.config['GROUPS'].values())
                    backup_data['groups'] = [
                        grp for grp in all_groups if grp['name'] in group_names
                    ]

            # 保存备份
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"备份完成: {backup_file}")
            return True
        except Exception as e:
            self.logger.error(f"备份失败: {e}")
            return False

    def remove_from_groups(self, prefix):
        """从地址组中移除指定前缀的地址"""
        try:
            self.logger.info(f"从地址组中移除 {prefix} 地址引用...")

            # 获取所有地址组
            url = f"{self.base_url}/cmdb/firewall/addrgrp"
            params = {'vdom': self.vdom}
            response = self.session.get(url, params=params, verify=False, timeout=30)

            if response.status_code != 200:
                return False

            result = response.json()
            if result.get('status') != 'success':
                return False

            groups = result.get('results', [])
            updated = 0

            for group in groups:
                group_name = group['name']
                members = group.get('member', [])

                # 过滤掉要删除的成员
                new_members = [m for m in members if not m['name'].startswith(f"{prefix}_")]

                # 如果成员有变化，更新地址组
                if len(new_members) != len(members):
                    if len(new_members) == 0:
                        # 如果会变空，使用占位符"all"（FortiGate内置地址对象）
                        self.logger.info(f"  地址组 {group_name} 会变空，使用占位符 'all'")
                        new_members = [{'name': 'all'}]

                    # 更新地址组
                    update_url = f"{self.base_url}/cmdb/firewall/addrgrp/{group_name}"
                    update_data = {'member': new_members}
                    resp = self.session.put(update_url, params=params, json=update_data, verify=False, timeout=30)

                    if resp.status_code == 200:
                        updated += 1
                        self.logger.info(f"  更新地址组 {group_name}: {len(members)} -> {len(new_members)} 成员")
                    else:
                        self.logger.warning(f"  更新地址组 {group_name} 失败")

            if updated > 0:
                self.logger.info(f"已更新 {updated} 个地址组")
                return True
            else:
                self.logger.info("无需更新地址组")
                return True

        except Exception as e:
            self.logger.error(f"从地址组移除引用失败: {e}")
            return False

    def delete_old_addresses(self, prefix):
        """删除旧的地址对象"""
        try:
            # 获取所有地址对象
            url = f"{self.base_url}/cmdb/firewall/address"
            params = {'vdom': self.vdom}
            response = self.session.get(url, params=params, verify=False, timeout=30)

            if response.status_code != 200:
                return 0

            result = response.json()
            if result.get('status') != 'success':
                return 0

            # 筛选要删除的地址
            addresses = result.get('results', [])
            to_delete = [addr['name'] for addr in addresses if addr['name'].startswith(f"{prefix}_")]

            if not to_delete:
                return 0

            self.logger.info(f"正在删除 {len(to_delete)} 个旧的 {prefix} 地址对象...")

            # 并发删除
            deleted = 0
            with ThreadPoolExecutor(max_workers=self.config['MAX_WORKERS']) as executor:
                futures = {executor.submit(self._delete_address, name): name for name in to_delete}

                for future in as_completed(futures):
                    if future.result():
                        deleted += 1

            self.logger.info(f"删除完成: {deleted}/{len(to_delete)}")
            return deleted
        except Exception as e:
            self.logger.error(f"删除旧地址异常: {e}")
            return 0

    def _delete_address(self, name):
        """删除单个地址对象"""
        url = f"{self.base_url}/cmdb/firewall/address/{name}"
        params = {'vdom': self.vdom}
        try:
            response = self.session.delete(url, params=params, verify=False, timeout=10)
            return response.status_code == 200
        except:
            return False

    def create_address(self, name, subnet, retry_on_timeout=True):
        """创建单个地址对象，支持超时重试"""
        url = f"{self.base_url}/cmdb/firewall/address"
        params = {'vdom': self.vdom}

        # 将 1.2.3.0/24 格式转换为 1.2.3.0 255.255.255.0 格式
        try:
            ip, mask_bits = subnet.split('/')
            mask_bits = int(mask_bits)

            # 计算子网掩码
            mask = (0xFFFFFFFF << (32 - mask_bits)) & 0xFFFFFFFF
            mask_str = f"{(mask >> 24) & 0xFF}.{(mask >> 16) & 0xFF}.{(mask >> 8) & 0xFF}.{mask & 0xFF}"

            data = {
                'name': name,
                'type': 'ipmask',
                'subnet': f"{ip} {mask_str}",
                'comment': f'Auto-created by CN IP Updater at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            }

            # 首次尝试
            response = self.session.post(url, params=params, json=data, verify=False, timeout=10)

            if response.status_code == 200:
                return True

            # 如果是超时或资源不足相关错误，且允许重试，则等待后重试一次
            if retry_on_timeout:
                try:
                    error_msg = response.json().get('error', '').lower() if response.status_code != 200 else ''
                    # 检测资源不足、超时等错误
                    if any(keyword in error_msg for keyword in ['timeout', 'resource', 'busy', 'overload']):
                        time.sleep(0.5)  # 短暂等待
                        response = self.session.post(url, params=params, json=data, verify=False, timeout=10)
                        return response.status_code == 200
                except:
                    pass

            return False

        except Exception as e:
            # 捕获超时异常，重试一次
            if retry_on_timeout and 'timeout' in str(e).lower():
                try:
                    time.sleep(0.5)
                    response = self.session.post(url, params=params, json=data, verify=False, timeout=10)
                    return response.status_code == 200
                except:
                    pass
            return False

    def batch_create_addresses(self, addresses):
        """批量创建地址对象，返回成功创建的地址名称列表"""
        self.logger.info(f"正在创建 {len(addresses)} 个地址对象...")

        created = 0
        failed = 0
        first_error = None
        successful_names = []  # 追踪成功创建的地址名称
        failed_addresses = []  # 追踪失败的地址

        with ThreadPoolExecutor(max_workers=self.config['MAX_WORKERS']) as executor:
            futures = {executor.submit(self.create_address, name, subnet): (name, subnet)
                      for name, subnet in addresses}

            for future in as_completed(futures):
                name, subnet = futures[future]
                try:
                    if future.result():
                        created += 1
                        successful_names.append(name)  # 记录成功的地址
                        if created % 100 == 0:
                            self.logger.info(f"  已创建 {created}/{len(addresses)}...")
                    else:
                        failed += 1
                        failed_addresses.append((name, subnet))
                        # 只记录第一个失败的详情用于调试
                        if failed == 1 and not first_error:
                            try:
                                # 尝试再次获取详细错误
                                url = f"{self.base_url}/cmdb/firewall/address"
                                params = {'vdom': self.vdom}
                                ip, mask_bits = subnet.split('/')
                                mask_bits = int(mask_bits)
                                mask = (0xFFFFFFFF << (32 - mask_bits)) & 0xFFFFFFFF
                                mask_str = f"{(mask >> 24) & 0xFF}.{(mask >> 16) & 0xFF}.{(mask >> 8) & 0xFF}.{mask & 0xFF}"
                                test_data = {'name': name, 'type': 'ipmask', 'subnet': f"{ip} {mask_str}"}
                                resp = self.session.post(url, params=params, json=test_data, verify=False, timeout=10)
                                first_error = resp.json() if resp.status_code != 200 else None
                            except:
                                pass
                except Exception as e:
                    failed += 1
                    failed_addresses.append((name, subnet))

        if first_error:
            self.logger.warning(f"  首个失败示例: {first_error}")

        # 如果有失败的地址，尝试重试一次
        if failed_addresses:
            self.logger.info(f"检测到 {len(failed_addresses)} 个失败地址，等待5秒后重试...")
            time.sleep(5)  # 给飞塔一些时间释放资源

            retry_created = 0
            self.logger.info(f"开始重试 {len(failed_addresses)} 个失败地址...")

            with ThreadPoolExecutor(max_workers=max(5, self.config['MAX_WORKERS'] // 2)) as executor:
                # 降低并发数重试
                retry_futures = {executor.submit(self.create_address, name, subnet, retry_on_timeout=False): (name, subnet)
                                for name, subnet in failed_addresses}

                for future in as_completed(retry_futures):
                    name, subnet = retry_futures[future]
                    try:
                        if future.result():
                            retry_created += 1
                            successful_names.append(name)
                            created += 1
                            failed -= 1
                            if retry_created % 50 == 0:
                                self.logger.info(f"  重试成功 {retry_created}/{len(failed_addresses)}...")
                    except:
                        pass

            if retry_created > 0:
                self.logger.info(f"重试完成: 成功 {retry_created}/{len(failed_addresses)}")

        self.logger.info(f"创建完成: 总成功 {created}, 最终失败 {failed}")
        return created, failed, successful_names

    def ensure_group_exists(self, group_name):
        """确保地址组存在"""
        url = f"{self.base_url}/cmdb/firewall/addrgrp/{group_name}"
        params = {'vdom': self.vdom}

        # 检查是否存在
        response = self.session.get(url, params=params, verify=False, timeout=10)
        if response.status_code == 200:
            self.logger.info(f"地址组 {group_name} 已存在")
            return True

        # 创建地址组
        url = f"{self.base_url}/cmdb/firewall/addrgrp"
        data = {
            'name': group_name,
            'member': [],
            'comment': 'Auto-created by CN IP Updater'
        }

        response = self.session.post(url, params=params, json=data, verify=False, timeout=10)
        if response.status_code == 200:
            self.logger.info(f"地址组 {group_name} 创建成功")
            return True
        else:
            self.logger.error(f"地址组 {group_name} 创建失败")
            return False

    def update_group_members(self, group_name, member_names):
        """一次性更新地址组成员（避免分批导致的越来越慢）"""
        url = f"{self.base_url}/cmdb/firewall/addrgrp/{group_name}"
        params = {'vdom': self.vdom}

        # 将成员名称转换为API需要的格式
        members = [{'name': name} for name in member_names]

        self.logger.info(f"开始更新地址组 {group_name}，共 {len(member_names)} 个成员")
        self.logger.info(f"⚠️ 使用一次性更新模式（不分批）")

        # 计算合理的超时时间：每1000条记录给30秒，最少3分钟
        timeout = max(180, (len(members) // 1000 + 1) * 30)
        self.logger.info(f"  设置超时时间：{timeout} 秒")

        # 一次性替换所有成员
        data = {'member': members}

        max_retries = 3
        for retry in range(max_retries):
            try:
                self.logger.info(f"  正在提交 {len(members)} 个成员到 FortiGate...")
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

    def update_single_isp(self, isp_key):
        """更新单个运营商的IP地址"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"开始更新 {isp_key}")
        self.logger.info(f"{'='*60}")

        # 1. 获取IP列表
        url = self.config['IP_SOURCES'][isp_key]
        ip_list = self.fetch_ip_list(url)

        if not ip_list:
            self.logger.error(f"{isp_key} IP列表为空，跳过")
            return {
                'isp': isp_key,
                'success': False,
                'total': 0,
                'created': 0,
                'failed': 0
            }

        # 2. 从地址组中移除旧地址引用
        self.remove_from_groups(isp_key)
        time.sleep(1)

        # 3. 删除旧地址对象
        deleted = self.delete_old_addresses(isp_key)

        # 等待一下，确保删除完成
        if deleted > 0:
            time.sleep(2)

        # 4. 创建新地址对象
        # 地址对象命名格式: CMCC_1.2.3.0_24 (斜杠替换为下划线)
        addresses = []
        for ip_cidr in ip_list:
            name = f"{isp_key}_{ip_cidr.replace('/', '_')}"
            addresses.append((name, ip_cidr))

        created, failed, successful_names = self.batch_create_addresses(addresses)

        # 5. 更新地址组
        group_name = self.config['GROUPS'][isp_key]
        self.ensure_group_exists(group_name)

        # 只将成功创建的地址加入组
        if created > 0:
            self.logger.info(f"将 {len(successful_names)} 个成功创建的地址加入组 {group_name}")
            self.update_group_members(group_name, successful_names)
        else:
            self.logger.warning(f"没有成功创建的地址，跳过更新地址组")

        self.logger.info(f"{isp_key} 更新完成\n")

        return {
            'isp': isp_key,
            'success': True,
            'total': len(ip_list),
            'created': created,
            'failed': failed,
            'deleted': deleted
        }

    def update_all(self):
        """更新所有运营商IP"""
        self.logger.info("\n" + "="*80)
        self.logger.info("飞塔防火墙中国IP地址更新任务开始")
        self.logger.info("="*80)

        start_time = datetime.now()

        # 1. 备份当前配置
        self.backup_current_config()

        # 2. 更新各运营商IP
        results = []
        for isp_key in ['CMCC', 'Unicom', 'Telecom', 'ALL-CN']:
            result = self.update_single_isp(isp_key)
            results.append(result)
            time.sleep(1)  # 间隔1秒，避免API请求过快

        # 3. 统计结果
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        total_created = sum(r['created'] for r in results)
        total_failed = sum(r['failed'] for r in results)
        total_deleted = sum(r.get('deleted', 0) for r in results)

        # 4. 输出汇总
        self.logger.info("\n" + "="*80)
        self.logger.info("更新任务完成")
        self.logger.info("="*80)
        self.logger.info(f"总耗时: {duration:.1f}秒")
        self.logger.info(f"删除地址: {total_deleted}")
        self.logger.info(f"创建地址: {total_created}")
        self.logger.info(f"失败地址: {total_failed}")

        for r in results:
            self.logger.info(f"  - {r['isp']}: 创建 {r['created']}/{r['total']}, 删除 {r.get('deleted', 0)}")

        # 5. 发送通知
        self._send_notification(results, duration)

        return results

    def _send_notification(self, results, duration):
        """发送更新通知"""
        total_created = sum(r['created'] for r in results)
        total_failed = sum(r['failed'] for r in results)

        status = "✅ 成功" if total_failed == 0 else "⚠️ 部分失败"

        content = f"""
**更新时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**耗时:** {duration:.1f}秒
**状态:** {status}

**统计信息:**
- 总创建: {total_created}
- 总失败: {total_failed}

**详细信息:**
"""
        for r in results:
            content += f"\n- **{r['isp']}**: 创建 {r['created']}/{r['total']}"

        self.notifier.send("飞塔防火墙IP更新完成", content)


def run_update():
    """执行更新任务"""
    try:
        logger = Logger(CONFIG['LOG_DIR'])
        updater = FortiGateIPUpdater(CONFIG, logger)
        updater.update_all()
    except Exception as e:
        logging.error(f"更新任务异常: {e}")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='飞塔防火墙中国IP地址自动更新服务')
    parser.add_argument('--now', action='store_true', help='立即执行一次更新')
    parser.add_argument('--once', action='store_true', help='只执行一次更新后退出（不启动定时任务）')
    args = parser.parse_args()

    print("="*80)
    print("飞塔防火墙中国IP地址自动更新服务")
    print("="*80)
    print(f"定时更新: 每天 {CONFIG['UPDATE_TIME']}")
    print(f"防火墙: {CONFIG['FW_HOST']}:{CONFIG['FW_PORT']}")
    print(f"日志目录: {CONFIG['LOG_DIR']}")
    print(f"备份目录: {CONFIG['BACKUP_DIR']}")
    print("="*80)

    # 如果指定了 --once，只执行一次后退出
    if args.once:
        print("\n执行单次更新任务...")
        run_update()
        print("\n更新完成，退出")
        return

    # 如果指定了 --now，立即执行一次
    if args.now:
        print("\n立即执行更新...")
        run_update()

    # 设置定时任务
    schedule.every().day.at(CONFIG['UPDATE_TIME']).do(run_update)

    print(f"\n定时任务已启动，将在每天 {CONFIG['UPDATE_TIME']} 自动更新")
    print("按 Ctrl+C 退出")

    # 循环运行
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        print("\n\n服务已停止")


if __name__ == "__main__":
    main()
