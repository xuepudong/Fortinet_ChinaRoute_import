#!/usr/bin/env python3
"""
飞塔防火墙地址对象快速清理脚本
用于批量删除所有带有"CN-"前缀的地址对象
"""

import requests
import urllib3
from requests.auth import HTTPBasicAuth
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class FortiGateAPI:
    def __init__(self, host, api_token=None, username=None, password=None, vdom='root', port=443):
        self.host = host
        self.api_token = api_token
        self.username = username
        self.password = password
        self.vdom = vdom
        self.base_url = f"https://{host}:{port}/api/v2"
        self.session = requests.Session()
        
        if api_token:
            self.session.headers.update({'Authorization': f'Bearer {api_token}'})
        elif username and password:
            self.session.auth = HTTPBasicAuth(username, password)
        else:
            raise ValueError("必须提供api_token或username/password")
    
    def get_all_data(self):
        """一次性获取所有需要的数据"""
        print("正在获取防火墙配置...")
        data = {
            'addresses': [],
            'addrgrps': [],
            'policies': []
        }
        
        # 获取地址对象
        try:
            url = f"{self.base_url}/cmdb/firewall/address"
            params = {'vdom': self.vdom}
            response = self.session.get(url, params=params, verify=False, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    data['addresses'] = result.get('results', [])
        except Exception as e:
            print(f"获取地址对象失败: {e}")
        
        # 获取地址组
        try:
            url = f"{self.base_url}/cmdb/firewall/addrgrp"
            params = {'vdom': self.vdom}
            response = self.session.get(url, params=params, verify=False, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    data['addrgrps'] = result.get('results', [])
        except Exception as e:
            print(f"获取地址组失败: {e}")
        
        # 获取策略
        try:
            url = f"{self.base_url}/cmdb/firewall/policy"
            params = {'vdom': self.vdom}
            response = self.session.get(url, params=params, verify=False, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    data['policies'] = result.get('results', [])
        except Exception as e:
            print(f"获取策略失败: {e}")
        
        return data
    
    def build_usage_map(self, data, prefix):
        """构建使用关系映射"""
        cn_addrs = {addr['name'] for addr in data['addresses'] if addr['name'].startswith(prefix)}
        usage_map = {name: {'groups': set(), 'policies_src': set(), 'policies_dst': set()} for name in cn_addrs}
        
        # 检查地址组
        for group in data['addrgrps']:
            group_name = group['name']
            members = {m['name'] for m in group.get('member', [])}
            for addr in cn_addrs & members:
                usage_map[addr]['groups'].add(group_name)
        
        # 检查策略
        for policy in data['policies']:
            policy_id = policy['policyid']
            src = {s['name'] for s in policy.get('srcaddr', [])}
            dst = {d['name'] for d in policy.get('dstaddr', [])}
            
            for addr in cn_addrs & src:
                usage_map[addr]['policies_src'].add(policy_id)
            for addr in cn_addrs & dst:
                usage_map[addr]['policies_dst'].add(policy_id)
        
        return usage_map
    
    def delete_addrgrp(self, name):
        """删除单个地址组"""
        url = f"{self.base_url}/cmdb/firewall/addrgrp/{name}"
        params = {'vdom': self.vdom}
        try:
            response = self.session.delete(url, params=params, verify=False, timeout=10)
            return response.status_code == 200
        except:
            return False

    def update_addrgrp(self, name, members):
        """更新单个地址组"""
        url = f"{self.base_url}/cmdb/firewall/addrgrp/{name}"
        params = {'vdom': self.vdom}
        try:
            response = self.session.put(url, params=params, json={'member': members}, verify=False, timeout=30)
            return response.status_code == 200
        except:
            return False

    def batch_update_groups(self, updates, deletes):
        """批量更新和删除地址组"""
        results = {'updated': 0, 'deleted': 0, 'failed': 0}

        # 先删除空组
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.delete_addrgrp, name): name for name in deletes}
            for future in as_completed(futures):
                try:
                    if future.result():
                        results['deleted'] += 1
                    else:
                        results['failed'] += 1
                except:
                    results['failed'] += 1

        # 再更新非空组
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.update_addrgrp, name, members): name
                      for name, members in updates.items()}
            for future in as_completed(futures):
                try:
                    if future.result():
                        results['updated'] += 1
                    else:
                        results['failed'] += 1
                except:
                    results['failed'] += 1

        return results
    
    def update_policy(self, policy_id, update_data):
        """更新单个策略"""
        url = f"{self.base_url}/cmdb/firewall/policy/{policy_id}"
        params = {'vdom': self.vdom}
        try:
            response = self.session.put(url, params=params, json=update_data, verify=False, timeout=30)
            return response.status_code == 200
        except:
            return False

    def batch_update_policies(self, updates):
        """并发批量更新策略"""
        results = {'success': 0, 'failed': 0}

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.update_policy, policy_id, data): policy_id
                      for policy_id, data in updates.items()}

            for future in as_completed(futures):
                try:
                    if future.result():
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                except:
                    results['failed'] += 1

        return results
    
    def delete_address(self, name):
        """删除单个地址"""
        url = f"{self.base_url}/cmdb/firewall/address/{name}"
        params = {'vdom': self.vdom}
        try:
            response = self.session.delete(url, params=params, verify=False, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def batch_delete_addresses(self, names, max_workers=20):
        """并发批量删除地址（带重试）"""
        results = {'success': 0, 'failed': 0}
        failed_names = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.delete_address, name): name for name in names}

            for future in as_completed(futures):
                name = futures[future]
                try:
                    if future.result():
                        results['success'] += 1
                        if results['success'] % 100 == 0:
                            print(f"  已删除 {results['success']}/{len(names)}...")
                    else:
                        failed_names.append(name)
                        results['failed'] += 1
                except:
                    failed_names.append(name)
                    results['failed'] += 1

        # 重试失败的
        if failed_names:
            print(f"\n  重试 {len(failed_names)} 个失败的地址...")
            import time
            time.sleep(2)  # 等待2秒

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(self.delete_address, name): name for name in failed_names}

                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        if future.result():
                            results['success'] += 1
                            results['failed'] -= 1
                    except:
                        pass

        return results
    
    def cleanup_fast(self, prefix='CN-', dry_run=True):
        """快速清理"""
        # 1. 获取所有数据
        data = self.get_all_data()
        cn_addrs = [addr for addr in data['addresses'] if addr['name'].startswith(prefix)]
        
        print(f"\n找到 {len(cn_addrs)} 个 {prefix} 地址对象")
        
        if not cn_addrs:
            print("没有需要删除的对象")
            return
        
        # 2. 构建使用映射
        print("分析使用情况...")
        usage_map = self.build_usage_map(data, prefix)
        
        # 统计
        used_count = sum(1 for u in usage_map.values() if u['groups'] or u['policies_src'] or u['policies_dst'])
        print(f"其中 {used_count} 个正在使用")
        
        if dry_run:
            print(f"\n{'='*60}")
            print("模拟运行 - 将要删除的地址:")
            for addr in cn_addrs[:20]:  # 只显示前20个
                name = addr['name']
                u = usage_map[name]
                status = ""
                if u['groups'] or u['policies_src'] or u['policies_dst']:
                    status = f" [用于 {len(u['groups'])}组 {len(u['policies_src'])+len(u['policies_dst'])}策略]"
                print(f"  {name}{status}")
            if len(cn_addrs) > 20:
                print(f"  ... 还有 {len(cn_addrs)-20} 个")
            print(f"{'='*60}")
            print("设置 dry_run=False 执行删除")
            return
        
        # 确认
        confirm = input(f"\n确认删除 {len(cn_addrs)} 个地址? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("已取消")
            return
        
        # 3. 批量处理地址组
        print("\n第1步: 处理地址组...")
        group_updates = {}
        group_deletes = []

        for group in data['addrgrps']:
            group_name = group['name']
            members = group.get('member', [])
            new_members = [m for m in members if not m['name'].startswith(prefix)]

            if len(new_members) != len(members):
                if len(new_members) == 0:
                    # 地址组会变空，需要删除
                    group_deletes.append(group_name)
                else:
                    # 还有其他成员，更新
                    group_updates[group_name] = new_members

        if group_updates or group_deletes:
            print(f"  - 需要删除 {len(group_deletes)} 个空地址组")
            print(f"  - 需要更新 {len(group_updates)} 个地址组")
            results = self.batch_update_groups(group_updates, group_deletes)
            print(f"  - 已删除: {results['deleted']}, 已更新: {results['updated']}, 失败: {results['failed']}")
        
        # 4. 批量处理策略（也要移除被删除的地址组）
        print("\n第2步: 处理防火墙策略...")
        deleted_groups_set = set(group_deletes)
        policy_updates = {}

        for policy in data['policies']:
            policy_id = policy['policyid']
            srcaddr = policy.get('srcaddr', [])
            dstaddr = policy.get('dstaddr', [])

            # 移除CN-地址和被删除的地址组
            new_src = [s for s in srcaddr if not s['name'].startswith(prefix) and s['name'] not in deleted_groups_set]
            new_dst = [d for d in dstaddr if not d['name'].startswith(prefix) and d['name'] not in deleted_groups_set]

            update = {}
            if len(new_src) != len(srcaddr):
                update['srcaddr'] = new_src if new_src else [{'name': 'all'}]
            if len(new_dst) != len(dstaddr):
                update['dstaddr'] = new_dst if new_dst else [{'name': 'all'}]

            if update:
                policy_updates[policy_id] = update

        if policy_updates:
            print(f"  - 需要更新 {len(policy_updates)} 个策略")
            results = self.batch_update_policies(policy_updates)
            print(f"  - 成功: {results['success']}, 失败: {results['failed']}")
        
        # 5. 并发删除地址
        print(f"\n第3步: 删除 {len(cn_addrs)} 个地址对象...")
        addr_names = [addr['name'] for addr in cn_addrs]
        results = self.batch_delete_addresses(addr_names, max_workers=20)

        print(f"\n{'='*60}")
        print(f"完成! 成功: {results['success']}, 失败: {results['failed']}")
        print(f"{'='*60}")


def main():
    print("="*60)
    print("飞塔防火墙地址对象快速清理工具")
    print("="*60)
    
    # 配置
    FW_HOST = "10.4.0.1"
    FW_PORT = 8443
    API_TOKEN = "Qsk7wwkh9g4rjxzbQp4wjhH7gq0smd"
    VDOM = "root"
    
    try:
        fg = FortiGateAPI(host=FW_HOST, api_token=API_TOKEN, vdom=VDOM, port=FW_PORT)
        
        # 快速清理
        fg.cleanup_fast(prefix='CN-', dry_run=False)  # 改成False执行删除
        
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()