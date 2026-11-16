# ⛔ 弃用记录(2026-11-16 VM 实测后)

**scrutiny 0.10.0 硬依赖 InfluxDB 2.x**(web 启动即检查 `localhost:8086/api/v2/setup`,
无禁用开关,二进制不内嵌时序库;上游部署形态 = scrutiny-web + influxdb 双容器)。
这违背本项目 deb 封装约束「不得依赖外部数据库服务」。0.8 之前版本无此依赖但已停止
维护,不值得封装。本仓封存留档,不提交应用中心。VM 实测细节:

- CLI 与文档不符:`scrutiny-web` 是子命令结构(`start --config`),collector 的
  `--config` 是 devices 文件、API 端点用 `--api-endpoint`;
- `smartctl` 采集侧完全正常(TOS 出厂 smartctl 7.5,自动发现 /dev/sda);
- 若未来上游提供 SQLite/内嵌时序模式,可解封本仓。

---

# tos-app-scrutiny

将 [Scrutiny](https://github.com/AnalogJ/scrutiny)(S.M.A.R.T. 磁盘健康仪表盘,MIT)打包为 [铁威马 TOS](https://www.terra-master.com) 应用中心 **deb 类应用**(x86_64 + aarch64 双架构)。

**这是什么**:TOS deb 元数据壳 + 可复现构建脚本。上游 `scrutiny-web` + `scrutiny-collector-metrics` 二进制(Release 资产,UPSTREAM 锁定 SHA256)原样打包,本仓只产出 TOS 平台元数据、systemd 单元/定时器与配置种子 —— 不修改任何上游代码。

| 项目 | 值 |
|---|---|
| 应用 ID | `scrutiny` |
| 应用形态 | deb 类 · **open_path 外开**(浏览器新标签页,frp 同款模式) |
| 仪表盘 | `http://<NAS>:18232`(scrutiny-web,内置前端 + SQLite 历史) |
| 服务 | `scrutiny-web.service`(长驻)+ `scrutiny-collector.timer` → `scrutiny-collector.service`(每日 02:30 采集 SMART,root 运行) |
| 配置 | `/etc/scrutiny/scrutiny.yaml`(首装种子,升级保留) |
| 数据 | `/var/lib/scrutiny`(数据库 + 日志) |
| 版本 | 0.10.0(见 [UPSTREAM](UPSTREAM) 锁定) |
| 上游许可证 | MIT(全文见 [LICENSE](LICENSE),义务见 [NOTICE](NOTICE);封装层 MIT) |
| 依赖 | `smartctl`(TOS 出厂自带;postinst 缺失时告警,仪表盘仍可用) |

## 双服务接线(open_path 三要素,frp 模式)

1. `config.ini`:`"open_path": true, "path": "http://${ip}:18232", "exec": true`;
2. 无 nginx conf(open_path 由平台直接跳转端口);
3. 服务:web(专用 `scrutiny` 系统用户,加固)+ collector timer(root,SMART 需真设备节点 `PrivateDevices=false`)。

collector 的 `api.endpoint` 固定 `http://127.0.0.1:18232`(上报本机 web);
磁盘列表留空 = 自动扫描全部 `/dev/disk/by-id`。

## 目录结构

```
tos-app-scrutiny/
├── config.ini                          # TOS 平台元数据(open_path 模式)
├── scrutiny.lang                       # 26 种语言(生成:scripts/make_lang.py)
├── packaging-extras/scrutiny.yaml.default  # 配置种子 → /etc/scrutiny/
├── UPSTREAM                            # 版本锁定(web/collector × 双架构 SHA256)
├── DEBIAN/                             # control + postinst(预检 smartctl)/prerm/postrm
├── init.d/
│   ├── scrutiny-web.service            # 仪表盘服务(加固)
│   ├── scrutiny-collector.service      # oneshot 采集(root,SMART ioctl)
│   └── scrutiny-collector.timer        # 每日 02:30(+Persistent 补跑)
├── images/icons/scrutiny.svg           # 原创图标(盘体 + 心跳)
├── scripts/                            # fetch/build_deb/unpack_check/validate/make_lang/bump
├── build.sh                            # 一键构建 ./build.sh [x86_64|aarch64]
├── LICENSE                             # 上游 MIT 全文
└── NOTICE                              # 归属与许可义务说明
```

## 本地构建

依赖:bash、curl、python3(任意平台;有 dpkg-deb 时自动优先)。

```bash
./build.sh                # 双架构(下载上游二进制 → 校验 → 打包 → 解包验证)
./scripts/validate.py     # 元数据校验
```

产物:`build/output/scrutiny_<platform>.deb` + `.sha256`(约 18MB)。
`build.sh` 自动执行 `scripts/unpack_check.py`:ar 成员、control 根布局、字段、
双 ELF 机器类型与可执行位全过才算完成。

> 国内网络下载上游资产慢时可用 `gh release download v0.10.0 -R AnalogJ/scrutiny`
> (走 api.github.com 资产通道)放入 `.upstream-cache/`,再写入 `.verified` 指纹。

## 上架 Checklist(内部奖励计划 · deb 档 60 元)

1. ☐ 推送本仓 GitHub(ericbyz/tos-app-scrutiny)+ 打 tag `v0.10.0`;
2. ☐ 提交前**刷新查重**(`scrutiny` / `Scrutiny`,2026-11-15 核验空白);
3. ☐ x86_64 与 ARM **分别创建应用**(独立 App ID、同一开发者账号);
4. ☐ 提交 Release 直链 + SHA256 + 上游源码仓 + 本仓构建脚本;
5. ☐ VM 实测:raw dpkg 安装 + 手动接线(runbook AdWall 流程),确认 `smartctl`
   存在、手动 `systemctl start scrutiny-collector.service` 采集一次、
   仪表盘出现磁盘卡片截图;
6. ☐ 《参与报名表》勾选 deb 档,附仓库链接;
7. ☐ 30 天内维护 Issues 响应。

## 合规声明

- 上游二进制**原样封装**(MIT),未修改任何上游代码,许可证全文随包分发;
- 安装包内容:上游 Release 二进制 + 本仓元数据,无其他二进制;
- 不收集任何用户数据;SMART 历史仅存于 NAS 本地 `/var/lib/scrutiny`。
