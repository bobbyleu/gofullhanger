# 格峰晾衣架集成

## 简介
这是一个用于Home Assistant的格峰晾衣架自定义集成，通过MQTT协议与晾衣架设备进行通信，支持HomeKit Bridge接入苹果家庭，支持Siri语音控制。

## 功能特性
- 支持晾衣架的打开、关闭、停止控制
- 支持MQTT协议通信
- 支持HomeKit Bridge接入
- 支持Siri语音控制
- 实时状态同步
- 自动重连机制

## 安装方法

### 通过HACS安装
1. 在HACS中添加自定义仓库：`bobbyleu/gofullhanger`
2. 选择类别：`integration`
3. 点击下载安装
4. 重启Home Assistant

### 手动安装
1. 下载最新版本的集成文件
2. 将`custom_components/gofullhanger`目录复制到Home Assistant的`custom_components`目录
3. 重启Home Assistant

## 配置
1. 在Home Assistant中进入"设置" -> "设备与服务" -> "添加集成"
2. 搜索"格峰晾衣架"
3. 按照配置向导完成设置，需要输入以下信息：
   - MQTT Broker地址
   - MQTT端口（默认1883）
   - MQTT用户名（可选）
   - MQTT密码（可选）
   - MQTT主题前缀（默认gofullhanger）

## MQTT主题结构
- 命令主题：`{topic_prefix}/{device_id}/command`
- 状态主题：`{topic_prefix}/{device_id}/state`
- 可用性主题：`{topic_prefix}/{device_id}/availability`

## 控制命令
- 打开（放下）：`open`
- 关闭（升起）：`close`
- 停止：`stop`

## 状态更新
- 可以通过发布消息到状态主题来更新设备状态
- 状态值可以是数字（0-4）或字符串（如"open"、"close"等）

## 可用性状态
- 在线：`online`
- 离线：`offline`

## 使用说明
### HomeKit接入
1. 在Home Assistant中启用HomeKit Bridge
2. 将晾衣架设备添加到HomeKit
3. 在苹果家庭App中添加设备
4. 使用Siri控制："打开晾衣架"、"关闭晾衣架"

### 自动化示例
```yaml
automation:
  - alias: "自动晾衣"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: cover.open_cover
        target:
          entity_id: cover.gofullhanger
```

## 故障排除
### 集成无法添加
- 检查网络连接
- 确认MQTT Broker正常运行
- 查看Home Assistant日志

### MQTT通信问题
- 检查MQTT Broker配置
- 确认主题设置正确
- 查看MQTT Broker日志

### Siri控制不响应
- 确认HomeKit Bridge正常工作
- 检查设备状态
- 重启Home Assistant

## 版本历史
- 2.0: 重构为MQTT版本，支持MQTT协议通信
- 1.0.6: 修复bug
- 1.0.5: 修复HACS集成问题
- 1.0.4: 增加重试机制和错误处理

## 许可证
MIT License

## 支持
- 问题反馈：[GitHub Issues](https://github.com/bobbyleu/gofullhanger/issues)
- 文档：[GitHub Wiki](https://github.com/bobbyleu/gofullhanger)
