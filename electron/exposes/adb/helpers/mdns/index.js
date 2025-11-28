import { exec as _exec } from 'node:child_process'
import util from 'node:util'
import { adbPath } from '$electron/configs/index.js'
import appStore from '$electron/helpers/store.js'

const exec = util.promisify(_exec)

/**
 * mDNS 自动发现管理器
 * 用于通过 mDNS 自动发现局域网中的 Android 设备
 */
class MdnsDiscovery {
  constructor() {
    this.isEnabled = false
    this.intervalId = null
    this.discoveredDevices = new Map()
    this.scanInterval = 3000 // 3秒扫描一次
    this.listeners = []
  }

  /**
   * 确保 mDNS daemon 已启用
   */
  async ensureMdnsEnabled() {
    try {
      // 设置环境变量
      process.env.ADB_MDNS_OPENSCREEN = '1'

      const execPath = appStore.get('common.adbPath') || adbPath

      // 检查 mDNS daemon 状态
      const { stdout } = await exec(`"${execPath}" mdns check`, {
        env: { ...process.env },
        shell: true,
      })

      if (stdout.includes('unavailable')) {
        console.warn('mDNS daemon is unavailable, attempting to restart ADB server...')
        
        // 重启 ADB server
        await exec(`"${execPath}" kill-server`, {
          env: { ...process.env },
          shell: true,
        })
        
        await new Promise(resolve => setTimeout(resolve, 1000))
        
        await exec(`"${execPath}" start-server`, {
          env: { ...process.env },
          shell: true,
        })

        await new Promise(resolve => setTimeout(resolve, 2000))

        // 再次检查
        const { stdout: checkAgain } = await exec(`"${execPath}" mdns check`, {
          env: { ...process.env },
          shell: true,
        })

        if (checkAgain.includes('unavailable')) {
          console.error('Failed to enable mDNS daemon')
          return false
        }
      }

      console.log('mDNS daemon is enabled:', stdout.trim())
      return true
    }
    catch (error) {
      console.error('Error ensuring mDNS enabled:', error.message)
      return false
    }
  }

  /**
   * 扫描 mDNS 服务
   */
  async scanServices() {
    try {
      const execPath = appStore.get('common.adbPath') || adbPath

      const { stdout, stderr } = await exec(`"${execPath}" mdns services`, {
        env: { ...process.env },
        shell: true,
        timeout: 8000,
      })

      if (stderr && !stderr.includes('daemon')) {
        console.warn('mDNS scan stderr:', stderr)
      }

      return this.parseServices(stdout)
    }
    catch (error) {
      if (error.message.includes('timeout')) {
        console.warn('mDNS scan timeout')
      }
      else {
        console.error('Error scanning mDNS services:', error.message)
      }
      return []
    }
  }

  /**
   * 解析 mDNS 服务输出
   * 输出格式: name\ttype\taddress
   */
  parseServices(output) {
    const devices = []
    const lines = output.split('\n')

    for (const line of lines) {
      const trimmed = line.trim()
      
      // 跳过标题行和空行
      if (!trimmed || trimmed.includes('List of') || trimmed.toLowerCase().includes('mdns services')) {
        continue
      }

      // 解析格式：name\ttype\taddress
      const parts = trimmed.split(/\s+/)
      if (parts.length >= 3) {
        const name = parts[0]
        const type = parts[1]
        const address = parts[2]

        // 只关注连接服务（已配对的设备）
        if (type.includes('_adb-tls-connect')) {
          // 解析 IP 和端口
          const [ip, port] = address.split(':')
          
          devices.push({
            name,
            type,
            ip,
            port: port ? parseInt(port) : null,
            address,
            discoveredAt: new Date().toISOString(),
          })
        }
      }
    }

    return devices
  }

  /**
   * 启动自动发现
   */
  async start() {
    if (this.isEnabled) {
      console.log('mDNS discovery is already running')
      return
    }

    // 确保 mDNS 已启用
    const enabled = await this.ensureMdnsEnabled()
    if (!enabled) {
      console.warn('Cannot start mDNS discovery: daemon not available')
      return false
    }

    this.isEnabled = true
    console.log('Starting mDNS auto-discovery...')

    // 立即扫描一次
    await this.scan()

    // 定期扫描
    this.intervalId = setInterval(async () => {
      await this.scan()
    }, this.scanInterval)

    return true
  }

  /**
   * 停止自动发现
   */
  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId)
      this.intervalId = null
    }
    this.isEnabled = false
    console.log('Stopped mDNS auto-discovery')
  }

  /**
   * 执行扫描并通知监听器
   */
  async scan() {
    const services = await this.scanServices()
    
    if (services.length > 0) {
      // 更新已发现设备列表
      const newDevices = []
      
      for (const service of services) {
        const key = service.address
        const existing = this.discoveredDevices.get(key)
        
        if (!existing) {
          newDevices.push(service)
          console.log(`Discovered new device via mDNS: ${service.name} at ${service.address}`)
        }
        
        this.discoveredDevices.set(key, service)
      }

      // 通知监听器
      if (newDevices.length > 0 || services.length > 0) {
        this.notifyListeners({
          type: 'devices-found',
          devices: services,
          newDevices,
        })
      }
    }

    // 清理超过30秒未发现的设备
    const now = Date.now()
    for (const [key, device] of this.discoveredDevices.entries()) {
      const age = now - new Date(device.discoveredAt).getTime()
      if (age > 30000) {
        this.discoveredDevices.delete(key)
        console.log(`Removed stale device: ${device.name}`)
      }
    }
  }

  /**
   * 添加监听器
   */
  on(listener) {
    this.listeners.push(listener)
  }

  /**
   * 移除监听器
   */
  off(listener) {
    const index = this.listeners.indexOf(listener)
    if (index > -1) {
      this.listeners.splice(index, 1)
    }
  }

  /**
   * 通知所有监听器
   */
  notifyListeners(event) {
    for (const listener of this.listeners) {
      try {
        listener(event)
      }
      catch (error) {
        console.error('Error in mDNS listener:', error)
      }
    }
  }

  /**
   * 获取当前发现的所有设备
   */
  getDiscoveredDevices() {
    return Array.from(this.discoveredDevices.values())
  }

  /**
   * 设置扫描间隔
   */
  setScanInterval(milliseconds) {
    this.scanInterval = milliseconds
    
    // 如果正在运行，重启定时器
    if (this.isEnabled) {
      this.stop()
      this.start()
    }
  }
}

// 创建单例
const mdnsDiscovery = new MdnsDiscovery()

export default mdnsDiscovery
