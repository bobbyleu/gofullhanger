# 格峰晾衣架 Home Assistant 集成 (gofullhanger)

通过逆向格峰（Ortron）App 通信协议实现的 Home Assistant 自定义集成，直连格峰云端长连接，实时同步晾衣架状态。

## 功能特性

- **升降控制**：打开（下降）、关闭（上升）、停止，支持 0–100% 位置反馈
- **实时状态**：基于服务端推送（`onDeviceStatusData`），无需轮询
- **自动重连**：断线后指数退避重连（5s → 60s），心跳保活（10s 间隔）
- **多设备支持**：一个账号下所有晾衣架自动发现
- **可选实体**：消毒 / 风干 / 烘干开关与 WiFi 信号强度传感器**默认禁用**，按需在 HA 界面手动启用（见下文）

## 安装方法

### 通过 HACS 安装
1. 在 HACS 中添加自定义仓库：`bobbyleu/gofullhanger`，类别选择 `Integration`
2. 搜索并下载「格峰晾衣架」
3. 重启 Home Assistant

### 手动安装
1. 将 `custom_components/gofullhanger` 目录复制到 Home Assistant 的 `custom_components` 目录
2. 重启 Home Assistant

> 要求 Home Assistant ≥ 2024.8（实体注册表默认禁用功能所需的最低版本）。

## 配置
1. 进入「设置」→「设备与服务」→「添加集成」
2. 搜索「格峰晾衣架」
3. 输入格峰 App 的**手机号和密码**（与 App 同一账号即可，设备自动发现）
4. 如需修改账号密码，在集成条目上选择「重新配置」

## 实体说明

| 实体 | 类型 | 默认状态 | 说明 |
| --- | --- | --- | --- |
| `cover.<设备名>` | Cover | 启用 | 打开=下降(putDown)，关闭=上升(raiseUp)，支持停止 |
| `switch.<设备名>_消毒` | Switch | **禁用** | 消毒功能（翻转语义） |
| `switch.<设备名>_风干` | Switch | **禁用** | 风干功能（翻转语义） |
| `switch.<设备名>_烘干` | Switch | **禁用** | 烘干功能（翻转语义） |
| `sensor.<设备名>_信号强度` | Sensor | **禁用** | WiFi RSSI (dBm)，诊断类信息 |

## 默认禁用的实体与启用方法

以下四类实体在首次添加时**默认禁用**（不会出现在界面上、不记录历史、不参与自动化）：

| 实体 | 默认禁用的原因 |
| --- | --- |
| 消毒 / 风干 / 烘干开关 | 仅升降的基础型号（如"一号"）硬件不支持，点击只会返回"操作失败"；带这些功能的高端机型才需要 |
| WiFi 信号强度 (RSSI) | 诊断类信息，日常几乎用不到，默认开启只会增加数据库噪音 |

**启用方法**（以消毒开关为例）：
1. 「设置」→「设备与服务」→ 选择「格峰晾衣架」→ 点对应设备（如"一号"）
2. 被禁用的实体显示为灰色，点击「消毒」开关实体 → 打开「启用」开关（或在「实体」页面勾选"显示禁用实体"后启用）
3. 启用后 HA 会自动重载集成，实体即刻可用

**说明**：
- 禁用状态保存在 HA 实体注册表中，**升级集成不会重置**你的选择
- 基础型号即使手动启用，点击后设备仍会返回"操作失败"（硬件限制，集成不报错、开关保持关闭）
- 如果全部设备都不需要这些实体，无需任何操作——默认就是干净的

## 协议说明（逆向结果）

- 云端地址：`main.ortron.cn:13015`（Pomelo over TCP）
- 握手：`{"sys":{"version":"0.3.0","type":"unity-socket"}}` → 心跳间隔 10s
- 登录：`connector.userEntryHandler.login`（需 `packageName:"ypr"` + `clientid`）
- 控制：`main.userHandler.remoteControll`，`props:[{name, method:"set", value}]`
- 位置语义（实测）：`0`=收起 / `1`=中位 / `2`=放下 / `3`=上升中 / `4`=下降中
- 指令：`putDown` 下降、`raiseUp` 上升、`stop` 停止、`close` 关闭功能、`sterilize`/`airdrying`/`drying` 功能翻转
- 设备为纯云端设备：App 无任何局域网控制协议（实测全端口扫描无 TCP 监听），必须经厂商云端

## 故障排除

- **添加集成时提示无法连接**：确认 HA 主机能访问 `main.ortron.cn:13015`（TCP 出网）
- **实体显示不可用**：设备离线或与云端断连，集成会自动重连
- **功能开关点了没反应**：基础型号（仅升降）不支持消毒/风干/烘干，属硬件限制。这类实体本就默认禁用，不需要的话在设备页面将其保持禁用即可
- **修改配置后不生效**：在集成条目上「重新配置」或重载集成

## 版本历史

### 2.1.0
- 消毒/风干/烘干开关、WiFi RSSI 传感器改为**默认禁用**（`entity_registry_enabled_default=False`），可在 HA 界面手动启用
- RSSI 传感器标注 `entity_category: diagnostic`
- 清理 switch 实体中从不生效的乐观更新死代码，`is_on` 直接读取设备上报
- 删除未使用的 `lighting` 协议常量（机型无照明硬件）
- manifest 声明最低 HA 版本 2024.8.0

### 2.0.0（相对 1.0.x 的完整重写）
- **修正状态语义 bug**：1.0.x 的 `is_closed` 判 `position=='1'`、`is_opened` 判 `'2'`，而实测 `1`=中位、`2`=放下——衣架收起时 HA 显示"打开"、降到中位反而显示"关闭"；且 `current_cover_position` 直接返回字符串 `"0"/"1"/"2"`，HA 百分比位置（0–100 整数）完全失效
- **心跳保活**：1.0.x 无心跳，约 30 秒被服务端断开；2.0.x 10s 心跳，实测 45s+ 稳定在线
- **自动重连**：1.0.x 仅启动时重试 3 次，运行中断开即永久掉线；2.0.x 断线指数退避重连（5s→60s）无限续命
- **推送驱动架构**：1.0.x 每台 cover 各听一个事件总线消息，仅更新 position 一个字段；2.0.x 用 DataUpdateCoordinator 统一分发完整设备状态（position/props/isOnline 等）
- **clientid 自动生成**：1.0.x 需用户手填 clientid（从 App 抓包获取，极易填错导致登录失败）；2.0.x 自动生成 uuid4 并持久化
- **消息 ID 编码修正**：1.0.x 用 4 位十六进制作消息 id（Pomelo 实际是 varint 编码），多条消息快速发送时 id 冲突会丢响应
- **登录加固**：1.0.x 登录失败/操作返回码非 200 时直接 `close()` 并退出程序；2.0.x 区分鉴权失败（`ConfigEntryAuthFailed`）与网络问题（`ConfigEntryNotReady`），错误密码在配置界面明确提示
- **新增 reconfigure 流程**：1.0.x 只有 options flow；2.0.x 支持「重新配置」改账号密码
- **新增实体**：消毒/风干/烘干开关、RSSI 传感器（2.1.0 起默认禁用）
- **多设备过滤**：按 `e_type="hanger"` + `e_model="hanger_ypr"` 双重过滤，射频型号（hanger_sp 等）不会误建实体
- **manifest 语义修正**：`cloud_polling` → `cloud_push`（实际是长连接推送，非轮询）

### 1.0.x
- 初版，基于抓包手工硬编码 hex 报文，无心跳无重连

## 许可证
MIT License

## 支持
- 问题反馈：[GitHub Issues](https://github.com/bobbyleu/gofullhanger/issues)
