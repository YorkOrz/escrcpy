#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADB mDNS 稳定性测试 - 多次开关无线调试测试
测试环境变量永久设置后是否稳定
"""

import subprocess
import time
import os
from datetime import datetime

def check_env_variable():
    """检查环境变量是否已设置"""
    value = os.environ.get('ADB_MDNS_OPENSCREEN', '')
    return value == '1'

def check_mdns_daemon():
    """检查 mDNS daemon 状态"""
    result = subprocess.run(['adb', 'mdns', 'check'], 
                          capture_output=True, 
                          text=True,
                          timeout=5)
    return 'unavailable' not in result.stdout.lower()

def scan_mdns_services(timeout=8):
    """扫描 mDNS 服务"""
    try:
        result = subprocess.run(['adb', 'mdns', 'services'], 
                              capture_output=True, 
                              text=True,
                              timeout=timeout)
        
        devices = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or 'List of' in line or 'mdns services' in line.lower():
                continue
            
            parts = line.split('\t')
            if len(parts) >= 3:
                devices.append({
                    'name': parts[0].strip(),
                    'type': parts[1].strip(),
                    'address': parts[2].strip()
                })
        
        return devices
    except subprocess.TimeoutExpired:
        print("    ⚠ 扫描超时")
        return None
    except Exception as e:
        print(f"    ⚠ 扫描错误: {e}")
        return None

print("="*70)
print("  ADB mDNS 稳定性测试 - 开关无线调试测试")
print("="*70)

# 1. 验证环境变量
print("\n[检查 1] 验证环境变量...")
if check_env_variable():
    print("    ✓ 环境变量 ADB_MDNS_OPENSCREEN = 1")
else:
    print("    ✗ 环境变量未设置或值不正确")
    print("\n请先永久设置环境变量:")
    print("  [System.Environment]::SetEnvironmentVariable('ADB_MDNS_OPENSCREEN', '1', 'User')")
    print("\n然后重启 PowerShell 窗口")
    exit(1)

# 2. 检查 mDNS daemon
print("\n[检查 2] 验证 mDNS daemon 状态...")
if check_mdns_daemon():
    print("    ✓ mDNS daemon 已启用")
else:
    print("    ✗ mDNS daemon 不可用")
    print("\n请重启 ADB server:")
    print("  adb kill-server")
    print("  adb start-server")
    exit(1)

print("\n" + "="*70)
print("  开始稳定性测试")
print("="*70)

print("\n测试说明:")
print("  1. 我会进行 5 轮测试")
print("  2. 每轮测试前，请按照提示操作手机")
print("  3. 测试你「关闭再打开」无线调试后，能否稳定被发现")
print("\n准备好了吗？")
input("按 Enter 键开始测试...")

test_results = []

for round_num in range(1, 6):
    print("\n" + "="*70)
    print(f"  第 {round_num}/5 轮测试")
    print("="*70)
    
    # 提示用户操作
    if round_num == 1:
        print("\n📱 请在手机上操作:")
        print("   1. 如果无线调试是开着的，先「关闭」它")
        print("   2. 等待 3 秒")
        print("   3. 然后「重新打开」无线调试")
    else:
        print("\n📱 请在手机上操作:")
        print("   1. 「关闭」无线调试")
        print("   2. 等待 3 秒")
        print("   3. 「重新打开」无线调试")
    
    input(f"\n操作完成后，按 Enter 开始第 {round_num} 轮扫描...")
    
    # 扫描阶段
    print(f"\n开始扫描... (最多尝试 10 次，每 3 秒一次)")
    
    found = False
    device_info = None
    scan_attempts = 0
    max_attempts = 10
    
    for attempt in range(1, max_attempts + 1):
        scan_attempts = attempt
        current_time = datetime.now().strftime('%H:%M:%S')
        print(f"  [{current_time}] 扫描 #{attempt}...", end=" ")
        
        devices = scan_mdns_services(timeout=8)
        
        if devices is None:
            print("超时")
            continue
        
        if len(devices) > 0:
            device_info = devices[0]
            print(f"✓ 发现设备!")
            print(f"      名称: {device_info['name']}")
            print(f"      地址: {device_info['address']}")
            found = True
            break
        else:
            print("✗ 未发现")
        
        if attempt < max_attempts:
            time.sleep(3)
    
    # 记录结果
    test_results.append({
        'round': round_num,
        'found': found,
        'attempts': scan_attempts,
        'device': device_info
    })
    
    if found:
        print(f"\n  ✓ 第 {round_num} 轮: 成功 (第 {scan_attempts} 次扫描发现)")
    else:
        print(f"\n  ✗ 第 {round_num} 轮: 失败 (扫描 {scan_attempts} 次未发现)")
    
    if round_num < 5:
        print("\n等待 5 秒后进行下一轮测试...")
        time.sleep(5)

# 最终报告
print("\n" + "="*70)
print("  测试结果汇总")
print("="*70)

success_count = sum(1 for r in test_results if r['found'])
total_count = len(test_results)
success_rate = (success_count / total_count) * 100

print(f"\n总测试轮数: {total_count}")
print(f"成功次数: {success_count}")
print(f"失败次数: {total_count - success_count}")
print(f"成功率: {success_rate:.1f}%")

print("\n详细结果:")
for result in test_results:
    status = "✓ 成功" if result['found'] else "✗ 失败"
    attempts = f"第{result['attempts']}次扫描" if result['found'] else f"扫描{result['attempts']}次"
    print(f"  第 {result['round']} 轮: {status} ({attempts})")
    if result['found'] and result['device']:
        print(f"          设备: {result['device']['name']}")
        print(f"          地址: {result['device']['address']}")

# 平均发现时间
if success_count > 0:
    avg_attempts = sum(r['attempts'] for r in test_results if r['found']) / success_count
    avg_time = avg_attempts * 3  # 每次间隔3秒
    print(f"\n平均发现时间: {avg_time:.1f} 秒 (平均 {avg_attempts:.1f} 次扫描)")

# 稳定性评估
print("\n" + "="*70)
print("  稳定性评估")
print("="*70)

if success_rate == 100:
    print("\n  🎉 优秀! 每次都能成功发现设备!")
    print("  mDNS 在你的网络环境下非常稳定。")
    print("\n  建议:")
    print("    - escrcpy/QtScrcpy 应该能稳定自动发现设备")
    print("    - 可以放心使用 mDNS 作为主要发现方式")
elif success_rate >= 80:
    print("\n  👍 良好! 大部分时候能发现设备")
    print("  mDNS 基本可用，偶尔可能需要多等几秒。")
    print("\n  建议:")
    print("    - 可以使用 mDNS，配合少量重试机制")
    print("    - 如果失败可以手动刷新设备列表")
elif success_rate >= 60:
    print("\n  ⚠ 一般。成功率不够稳定")
    print("  可能的原因:")
    print("    - 路由器对 mDNS 支持不稳定")
    print("    - 网络质量波动")
    print("\n  建议:")
    print("    - 考虑使用端口扫描作为备选方案")
    print("    - 或使用 QR 码配对 + 固定地址连接")
else:
    print("\n  ✗ 较差。不建议依赖 mDNS")
    print("  可能的原因:")
    print("    - 路由器禁用了 mDNS 组播")
    print("    - 防火墙阻止 UDP 5353")
    print("    - 网络环境不支持 mDNS")
    print("\n  建议:")
    print("    - 使用端口扫描方案替代 mDNS")
    print("    - 或使用 USB 首次连接 + 记住 IP 地址")

print("\n" + "="*70)
print("测试完成!")
print("="*70)
