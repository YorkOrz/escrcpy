# mDNS 功能与上游同步策略

## 📝 概述

为了确保能够顺利同步上游 escrcpy 代码，我们采用**最小侵入式**的集成方式。

## 🔧 修改的文件清单

### 新增文件（不会冲突）
```
electron/exposes/adb/helpers/mdns/index.js  ← 新建，独立模块
MDNS_SOLUTION.md                            ← 文档
MDNS_INTEGRATION.md                         ← 文档  
MDNS_TESTING.md                             ← 文档
```

### 修改的文件（可能冲突）
```
electron/exposes/adb/index.js               ← 需要注意
```

## 🎯 推荐方案：将 mDNS 做成可选功能

### 方案 A：使用配置开关（推荐）

修改 `electron/exposes/adb/index.js`，使 mDNS 成为可选功能：

```javascript
// 在 init 函数中添加配置检查
async function init() {
  const bin = appStore.get('common.adbPath') || adbPath

  client = Adb.createClient({
    bin,
  })

  // 检查是否启用 mDNS 自动发现（可配置）
  const enableMdns = appStore.get('common.enableMdnsDiscovery', true) // 默认启用
  
  if (enableMdns) {
    try {
      const { default: mdnsDiscovery } = await import('./helpers/mdns/index.js')
      const mdnsEnabled = await mdnsDiscovery.start()
      
      if (mdnsEnabled) {
        console.log('mDNS auto-discovery started successfully')
        
        mdnsDiscovery.on(async (event) => {
          if (event.type === 'devices-found' && event.newDevices.length > 0) {
            console.log('New devices found via mDNS:', event.newDevices)
            
            for (const device of event.newDevices) {
              try {
                if (device.address) {
                  console.log(`Auto-connecting to ${device.name} at ${device.address}...`)
                  await connect(device.ip, device.port)
                  console.log(`Successfully connected to ${device.name}`)
                }
              }
              catch (error) {
                console.error(`Failed to auto-connect to ${device.name}:`, error.message)
              }
            }
          }
        })
        
        // 保存 mdnsDiscovery 实例以便导出
        global.mdnsDiscovery = mdnsDiscovery
      }
    }
    catch (error) {
      console.warn('Failed to initialize mDNS discovery:', error.message)
    }
  }
}
```

优点：
- ✅ 可以通过配置关闭，不影响原有功能
- ✅ 使用动态 import，如果文件不存在也不会报错
- ✅ 错误处理完善，失败也不影响主功能

### 方案 B：完全独立的插件（最安全）

创建一个完全独立的插件文件，在应用层面集成：

```
electron/plugins/mdns-discovery.js  ← 独立插件
```

然后在应用启动时加载：

```javascript
// electron/main/index.js 或其他入口文件
try {
  const { initMdnsPlugin } = await import('./plugins/mdns-discovery.js')
  await initMdnsPlugin()
}
catch (error) {
  console.warn('mDNS plugin not available:', error.message)
}
```

## 🔄 合并上游更新的策略

### 1. 使用 Git 保护分支

创建专门的分支管理：

```bash
# 主分支：跟踪上游
git checkout main
git remote add upstream https://github.com/viarotel-org/escrcpy.git
git fetch upstream
git merge upstream/main

# 功能分支：包含 mDNS 功能
git checkout -b feature/mdns-discovery
# 将 mDNS 相关代码提交到这个分支
```

### 2. 使用补丁方式

创建补丁文件，便于在合并后重新应用：

```bash
# 生成补丁
git diff main feature/mdns-discovery > mdns-discovery.patch

# 同步上游后重新应用
git checkout main
git pull upstream main
git apply mdns-discovery.patch
```

### 3. 使用 Git Rebase

```bash
# 在功能分支上
git checkout feature/mdns-discovery
git rebase main

# 如果有冲突，解决后继续
git rebase --continue
```

## 📋 冲突处理指南

### 如果 `electron/exposes/adb/index.js` 冲突

1. **查看冲突部分**
   ```bash
   git status
   git diff electron/exposes/adb/index.js
   ```

2. **手动合并**
   - 保留上游的所有更改
   - 在合适的位置重新添加 mDNS 相关代码
   - 通常是在 `init()` 函数和 `export default` 部分

3. **验证修改**
   ```bash
   pnpm dev
   # 测试 mDNS 功能是否正常
   ```

## 🛡️ 最小修改版本

如果你想最小化修改，只需修改这两个地方：

### 修改 1：导入（在文件顶部）
```javascript
import mdnsDiscovery from './helpers/mdns/index.js'  // 添加这一行
```

### 修改 2：初始化（在 init 函数中）
```javascript
async function init() {
  // ... 原有代码 ...
  
  // === mDNS 集成开始 ===
  const mdnsEnabled = await mdnsDiscovery.start()
  if (mdnsEnabled) {
    mdnsDiscovery.on(async (event) => {
      if (event.type === 'devices-found' && event.newDevices.length > 0) {
        for (const device of event.newDevices) {
          try {
            await connect(device.ip, device.port)
          } catch {}
        }
      }
    })
  }
  // === mDNS 集成结束 ===
}
```

这样修改的地方用注释标记清楚，合并时很容易识别和重新应用。

## 📝 建议的工作流程

1. **保持两个分支**
   - `main`: 纯净的上游同步分支
   - `feature/mdns`: 包含 mDNS 功能的分支

2. **定期同步**
   ```bash
   # 每周或每月同步一次上游
   git checkout main
   git fetch upstream
   git merge upstream/main
   git push origin main
   
   # 将更新合并到功能分支
   git checkout feature/mdns
   git rebase main
   # 解决冲突（如果有）
   git push origin feature/mdns --force-with-lease
   ```

3. **日常开发**
   - 在 `feature/mdns` 分支上开发
   - 提交 PR 时基于 `feature/mdns`

## 🎁 自动化脚本

创建一个同步脚本 `sync-upstream.sh`:

```bash
#!/bin/bash
# 同步上游并重新应用 mDNS 功能

echo "🔄 同步上游 escrcpy..."

# 切换到主分支
git checkout main

# 拉取上游更新
git fetch upstream
git merge upstream/main

# 切换回功能分支
git checkout feature/mdns

# 重新基于最新主分支
echo "🔧 重新应用 mDNS 功能..."
git rebase main

echo "✅ 同步完成！"
echo "💡 如果有冲突，请手动解决后执行: git rebase --continue"
```

## 🚀 向上游贡献

如果你想将 mDNS 功能贡献回上游：

1. **准备 PR**
   - 确保代码质量和文档完整
   - 添加测试用例
   - 遵循上游的代码规范

2. **提交 PR 说明**
```markdown
## 添加 mDNS 自动设备发现功能

### 功能说明
- 自动启用 ADB mDNS daemon
- 每 3 秒自动扫描局域网设备
- 自动连接发现的设备

### 测试结果
- 5 轮测试，100% 成功率
- 发现时间：3-6 秒
- 性能影响：可忽略

### 相关 Issue
解决了用户反馈的无线调试不稳定问题

### 截图
[截图]
```

## 📌 总结

**推荐做法**：
1. ✅ 使用方案 A（配置开关），最小修改
2. ✅ 保持 `main` 和 `feature/mdns` 两个分支
3. ✅ 使用注释标记修改位置
4. ✅ 定期 rebase 而不是 merge

这样既能使用 mDNS 功能，又能顺利同步上游更新！
