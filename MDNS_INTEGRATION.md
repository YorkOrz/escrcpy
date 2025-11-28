# mDNS 自动发现功能集成文档

## 📋 已完成的集成

### 1. 文件结构
```
electron/exposes/adb/
├── index.js                    # 主 ADB 模块（已修改）
└── helpers/
    └── mdns/
        └── index.js            # mDNS 自动发现模块（新建）
```

### 2. 集成的功能

#### ✅ 自动启用 mDNS
- 在 `adb.init()` 时自动设置环境变量 `ADB_MDNS_OPENSCREEN=1`
- 自动检测并重启 ADB server（如果需要）
- 验证 mDNS daemon 是否正常运行

#### ✅ 自动扫描设备
- 每 3 秒自动扫描一次 mDNS 服务
- 记录发现的设备信息（名称、IP、端口）
- 自动清理超过 30 秒未发现的陈旧设备

#### ✅ 自动连接设备
- 当发现新设备时，自动调用 `adb connect`
- 连接成功后，设备会出现在设备列表
- 连接失败会记录日志但不影响其他设备

#### ✅ 生命周期管理
- 随 escrcpy 启动而启动
- 随 escrcpy 关闭而停止
- 支持手动启动/停止

## 🎯 工作流程

### 用户操作流程
1. 启动 escrcpy 应用
2. 在手机上打开「无线调试」
3. **3-6 秒内自动连接** 🎉
4. 设备出现在设备列表
5. 可以正常使用 scrcpy 功能

### 技术流程
```
escrcpy 启动
    ↓
adb.init()
    ↓
设置 ADB_MDNS_OPENSCREEN=1
    ↓
启动 ADB server (mDNS enabled)
    ↓
启动 mDNS 自动发现
    ↓
每 3 秒扫描 mDNS 服务
    ↓
发现新设备 → 自动 adb connect
    ↓
设备出现在列表
```

## 📝 API 说明

### 新增的 API

```javascript
// 在渲染进程中可用
const adb = window.$adb

// 启动 mDNS 自动发现（已在 init 时自动调用）
await adb.startMdnsDiscovery()

// 停止 mDNS 自动发现
adb.stopMdnsDiscovery()

// 获取当前通过 mDNS 发现的设备
const devices = adb.getMdnsDevices()
// 返回: [{ name, type, ip, port, address, discoveredAt }]

// 设置扫描间隔（毫秒）
adb.setMdnsScanInterval(5000) // 改为 5 秒扫描一次

// 直接访问 mdnsDiscovery 实例
adb.mdnsDiscovery.on((event) => {
  console.log('mDNS event:', event)
})
```

## 🔧 配置选项

### 环境变量
- `ADB_MDNS_OPENSCREEN=1` - 自动设置，无需手动配置

### 可调整参数

在 `electron/exposes/adb/helpers/mdns/index.js` 中：

```javascript
// 扫描间隔（毫秒）
this.scanInterval = 3000  // 默认 3 秒

// 设备过期时间（毫秒）
const staleAge = 30000    // 默认 30 秒

// 扫描超时（毫秒）
timeout: 8000             // 默认 8 秒
```

## 🎛️ UI 集成建议

### 1. 显示 mDNS 状态

在设备列表页面添加状态指示器：

```vue
<template>
  <div class="mdns-status">
    <el-tag :type="mdnsStatus.enabled ? 'success' : 'info'">
      mDNS: {{ mdnsStatus.enabled ? '已启用' : '未启用' }}
    </el-tag>
    <span v-if="mdnsStatus.enabled">
      已发现 {{ mdnsDevices.length }} 个设备
    </span>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const mdnsStatus = ref({ enabled: false })
const mdnsDevices = ref([])

onMounted(async () => {
  // 检查 mDNS 状态
  mdnsStatus.value.enabled = window.$adb.mdnsDiscovery.isEnabled
  
  // 定期更新发现的设备
  setInterval(() => {
    mdnsDevices.value = window.$adb.getMdnsDevices()
  }, 3000)
})
</script>
```

### 2. 添加手动控制按钮

```vue
<el-button 
  @click="toggleMdns"
  :type="mdnsEnabled ? 'success' : 'default'"
>
  {{ mdnsEnabled ? '停止自动发现' : '启动自动发现' }}
</el-button>

<script setup>
const toggleMdns = async () => {
  if (mdnsEnabled.value) {
    window.$adb.stopMdnsDiscovery()
    mdnsEnabled.value = false
  } else {
    await window.$adb.startMdnsDiscovery()
    mdnsEnabled.value = true
  }
}
</script>
```

### 3. 显示设备发现动画

当通过 mDNS 发现设备时，显示通知：

```javascript
window.$adb.mdnsDiscovery.on((event) => {
  if (event.type === 'devices-found' && event.newDevices.length > 0) {
    event.newDevices.forEach(device => {
      ElNotification({
        title: '发现新设备',
        message: `${device.name}\n${device.address}`,
        type: 'success',
        duration: 3000,
      })
    })
  }
})
```

## 🧪 测试验证

### 1. 基础功能测试

```javascript
// 在开发者工具控制台中执行

// 检查 mDNS 是否启用
console.log('mDNS enabled:', window.$adb.mdnsDiscovery.isEnabled)

// 获取发现的设备
console.log('Discovered devices:', window.$adb.getMdnsDevices())

// 监听设备发现事件
window.$adb.mdnsDiscovery.on((event) => {
  console.log('mDNS event:', event)
})
```

### 2. 完整流程测试

1. 启动 escrcpy
2. 打开开发者工具，查看控制台
3. 在手机上打开无线调试
4. 观察控制台输出：
   ```
   mDNS auto-discovery started successfully
   Discovered new device via mDNS: adb-xxx at 192.168.x.x:xxxxx
   Auto-connecting to adb-xxx at 192.168.x.x:xxxxx...
   Successfully connected to adb-xxx
   ```
5. 检查设备列表是否出现新设备

## ⚠️ 注意事项

### 1. 首次使用需要配对
- 如果手机从未与 PC 配对过，需要先使用「QR 码配对」或「配对码配对」
- 配对成功后，后续每次打开无线调试都会自动连接

### 2. 网络要求
- 手机和 PC 必须在同一局域网
- 路由器需要支持 mDNS 广播（大部分路由器默认支持）
- 防火墙不能阻止 UDP 5353 端口

### 3. ADB 版本要求
- ADB 版本需要 31.0.2+
- escrcpy 自带的 ADB 版本应该满足要求

### 4. 性能影响
- 每 3 秒一次扫描，对性能影响很小
- 如果觉得扫描太频繁，可以调整间隔：
  ```javascript
  window.$adb.setMdnsScanInterval(5000) // 改为 5 秒
  ```

## 🐛 故障排查

### 问题：mDNS daemon 启动失败

**症状**：控制台显示 "mDNS auto-discovery failed to start"

**解决方案**：
1. 检查 ADB 版本：`adb version`（需要 >= 31.0.2）
2. 手动重启 ADB server：
   ```bash
   adb kill-server
   adb start-server
   adb mdns check
   ```
3. 检查环境变量是否设置：
   ```powershell
   $env:ADB_MDNS_OPENSCREEN
   ```

### 问题：发现设备但无法连接

**症状**：看到 "Discovered new device" 但 "Failed to auto-connect"

**原因**：设备未配对

**解决方案**：
1. 在 escrcpy 中使用「扫描二维码连接」功能
2. 或使用「配对码连接」功能
3. 配对成功后会自动连接

### 问题：从不发现任何设备

**症状**：一直显示扫描，但从未发现设备

**可能原因**：
1. 手机未打开无线调试
2. 手机和 PC 不在同一网络
3. 路由器禁用了 mDNS

**解决方案**：
1. 确认手机「无线调试」已开启
2. 确认手机和 PC 的 IP 在同一网段
3. 尝试在同一网络下用其他设备测试 mDNS

## 📊 日志说明

### 正常运行日志
```
mDNS auto-discovery started successfully
Discovered new device via mDNS: adb-32214939-sx2sW3 at 192.168.2.4:38961
Auto-connecting to adb-32214939-sx2sW3 at 192.168.2.4:38961...
Successfully connected to adb-32214939-sx2sW3
```

### 警告日志
```
mDNS scan timeout
Removed stale device: adb-xxx
```

### 错误日志
```
Failed to enable mDNS daemon
Failed to auto-connect to xxx: connection refused
```

## 🎉 完成！

现在你的 escrcpy fork 已经集成了 mDNS 自动发现功能！

**效果**：只要 escrcpy 在运行，每次在手机上打开无线调试，都会在 3-6 秒内自动连接并出现在设备列表中！
