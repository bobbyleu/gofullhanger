# 格峰晾衣架 Home Assistant 集成 (gofullhanger)

通过逆向格峰（Ortron）App 通信协议实现的 Home Assistant 自定义集成，直连格峰云端长连接，实时同步晾衣架状态。

## 功能特性

- **升降控制**：打开（下降）、关闭（上升）、停止，支持 0–100% 位置反馈
- **功能开关**：消毒 / 风干 / 烘干（部分基础型号仅支持升降，功能开关会优雅降级）
- **实时状态**：基于服务端推送（`onDeviceStatusData`），无需轮询
- **信号强度**：设备 WiFi RSSI 传感器
- **自动重连**：断线后指数退避重连（5s → 60s），心跳保活（10s 间隔）
- **多设备支持**：一个账号下所有晾衣架自动发现

## 安装方法

### 通过 HACS 安装
1. 在 HACS 中添加自定义仓库：`bobbyleu/gofullhanger`，类别选择 `Integration`
2. 搜索并下载「格峰晾衣架」
3. 重启 Home Assistant

### 手动安装
1. 将 `custom_components/gofullhanger` 目录复制到 Home Assistant 的 `custom_components` 目录
2. 重启 Home Assistant

## 配置
1. 进入「设置」→「设备与服务」→「添加集成」
2. 搜索「格峰晾衣架」
3. 输入格峰 App 的**手机号和密码**（与 App 同一账号即可，设备自动发现）
4. 如需修改账号密码，在集成条目上选择「重新配置」

## 实体说明

| 实体 | 类型 | 说明 |
| --- | --- | --- |
| `cover.<设备名>` |  Cover | 打开=下降(putDown)，关闭=上升(raiseUp)，支持停止 |
| `switch.<设备名>_消毒` | Switch | 消毒功能（翻转语义） |
| `switch.<设备名>_风干` | Switch | 风干功能（翻转语义） |
| `switch.<设备名>_烘干` | Switch | 烘干功能（翻转语义） |
| `sensor.<设备名>_信号强度` | Sensor | WiFi RSSI (dBm) |

## 协议说明（逆向结果）

- 云端地址：`main.ortron.cn:13015`（Pomelo over TCP）
- 握手：`{"sys":{"version":"0.3.0","type":"unity-socket"}}` → 心跳间隔 10s
- 登录：`connector.userEntryHandler.login`（需 `packageName:"ypr"` + `clientid`）
- 控制：`main.userHandler.remoteControll`，`props:[{name, method:"set", value}]`
- 位置语义（实测）：`0`=收起 / `1`=中位 / `2`=放下 / `3`=上升中 / `4`=下降中
- 指令：`putDown` 下降、`raiseUp` 上升、`stop` 停止、`close` 关闭功能、`sterilize`/`airdrying`/`drying` 功能翻转

## 故障排除

- **添加集成时提示无法连接**：确认 HA 主机能访问 `main.ortron.cn:13015`（TCP 出网）
- **实体显示不可用**：设备离线或与云端断连，集成会自动重连
- **功能开关无反应**：基础型号（仅升降）不支持消毒/风干/烘干，属正常现象

## 版本历史
- **2.0.0**：完整重写。修正位置语义（0=收起/2=放下）、新增 10s 心跳与自动重连、clientid 自动生成、推送驱动实时更新、config flow 仅需手机号+密码
- 1.0.x：初版

## 许可证
MIT License

## 支持
- 问题反馈：[GitHub Issues](https://github.com/bobbyleu/gofullhanger/issues)
