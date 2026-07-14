<div align="center">

  # ARL-Next
  **自动化资产侦察与漏洞监控平台**

  <p>
    <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/docker-ready-blue.svg?style=flat-square&logo=docker" alt="Docker"></a>
    <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/vue-3.x-4fc08d?style=flat-square&logo=vuedotjs" alt="Vue">
  </p>
</div>

<br/>

---

## 💡 什么是 ARL-Next？

**ARL-Next** 是 ARL (资产侦察灯塔) 的现代化重构版本，提供**极简、高效的自动化资产发现与漏洞监控方案**。其核心亮点包括：

* **引擎代际更替**：淘汰 PhantomJS，平滑升级为 Chromium + Puppeteer 动态爬虫与最新的 Nuclei 漏洞扫描引擎。
* **多维资产闭环**：打通“边界 ➔ 拓扑 ➔ 指纹 ➔ 漏洞”闭环，集成 ICP 与天眼查，支持拉取企业旗下 APP、小程序、公众号及微博等多元资产。
* **持续安全监控**：内置github最新 CVE 漏洞追踪与 Github 代码泄露实时监控能力，实现威胁前置。
* **部署与运维极简**：生产级脚本支持环境自检、内核网络调优及**全自动一键平滑升级**；开发环境支持代码卷挂载与 Vite 极速热更新，天然适配 AI 辅助开发。

---

## 📸 界面预览

* **全局仪表盘**：实时展示系统资源消耗、后台任务状态、多维资产与风险统计（含7天趋势）及最新系统日志流。
  <br><img src="./img/dashboard1.png" alt="仪表盘" width="800"><br>

* **企业资产查询**：支持 ICP 备案与天眼查关联检索，一键同步资产（网站/小程序/APP/公众号/微博）下发扫描任务。
  <br><img src="./img/enterprise-asset-search.png" alt="ICP备案查询" width="800"><br>

* **任务管理**：支持扫描任务全生命周期追踪、POC 插件按需自由组合与多维资产过滤。
  <br><img src="./img/task-new.png" alt="任务新建" width="800"><br>
  <br><img src="./img/task-management1.png" alt="任务管理" width="800"><br>

* **安全监控**：支持最新 CVE 漏洞监控与 Github 代码泄露监控。
  <br><img src="./img/threat-intel-radar.png" alt="安全监控" width="800"><br>

* **系统设置**：集成 Fofa/天眼查 API 热配置、字典云端热更新、扫描并发调度微调，以及六大告警通道（钉钉/飞书/企微/Telegram/邮件/Webhook）一键测试。
  <br><img src="./img/system-settings.png" alt="系统设置" width="800"><br>

---

## 🏗️ 架构设计

ARL-Next 采用前后端解耦的微服务架构，核心模块及版本如下：

1. **展示层 (Frontend)**：基于 **Vue 3.5** + **Vite 5.4** + **Ant Design Vue 4.2** 构建，生产环境由 **Nginx (Alpine)** 托管并提供 HTTPS 安全网关。
2. **业务 API 层 (Backend)**：基于 **Python 3.8+** 与 **Flask 2.0**，处理 JWT 权限鉴定、网关分发与本地化备案查询微服务。
3. **消息队列 (Broker)**：采用 **RabbitMQ 3.x**，实现 API 服务与异步高并发扫描任务之间的解耦分发。
4. **任务执行层 (Workers)**：基于 **Celery 5.2** 的分布式集群（含普通任务 Worker 与 Celery Beat 定时调度），负责运行 **Nuclei 3.11** 漏洞扫描、子域名爆破以及 **CVE/Github 实时监控**等底层任务。
5. **数据存储 (Database)**：使用 **MongoDB 4.0**，承载千万级大宽表资产数据与漏洞结果落地。

---

## 🚀 部署指南

### 开发环境部署 (前端本地 + Docker后端)

* **适用群体**：二开人员与安全研究者。
* **核心优势**：前后端彻底解耦；后端全栈容器化配合代码卷热更，前端 Vite 极速重载。
* **前置条件**：已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)、[Node.js](https://nodejs.org/)，并配置 `npm i -g pnpm`。

#### 🚀 一键启动

```bash
git clone https://github.com/owl234/ARL-Next && cd ARL-Next
bash start-dev.sh # 自动拉起后端、安装前端依赖并启动服务
```
访问 `http://localhost:5173` 开始开发（默认凭据：`admin` / `arlpass`）。

> 💡 **开发备注**：
> * **双端热重载**：后端修改本地代码即时生效，前端 Vite 实时热更。
> * **API与安全**：后端接口暴露于 `5001` 端口（前端已配反代）；若需 HTTPS，将 `mkcert` 证书命名为 `localhost.pem` / `localhost-key.pem` 放入 `certs/` 即可。

#### 🛠️ 常用命令

```bash
# 查看状态 / 实时查看核心日志 / 停止开发环境
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs -f arl-web arl-worker
docker compose -f docker-compose.dev.yml down
```

---

### 生产部署 (公网极速一键部署) ⭐ 推荐

**适用场景**：国内云服务器、企业内网。
**基准测试**：低配裸机 (2核4G, 5M带宽) 从零部署耗时约 **13.5分钟**；若自带 Docker 则压缩至 **2分钟**。

**核心优势**：
* **国内满速**：直连阿里云公开镜像库。
* **极度轻量**：剔除冗余编译链，镜像硬核减重超 700MB。
* **免密零配置**：免账号、免环境配置、免 `docker login`。
* **开箱即安全**：自动签发 10 年期 SSL，核心组件全内网隔离。
* **一键热升级**：内置独立守护进程，支持从 Web 端一键自动拉取新版并平滑重启，免人工 SSH 干预。

#### 🚀 部署步骤

```bash
git clone --depth 1 https://github.com/owl234/ARL-Next.git && cd ARL-Next
sudo bash start-prod.sh  # 一键拉起环境与SSL配置
```
访问 `https://<你的服务器IP>:5173` 即可登录（首次自签名证书请忽略不安全提示）。

> ⚙️ **商业证书替换**：将证书重命名为 `arl.crt` 和 `arl.key` 放至 `ssl-certs/` 目录，重新执行 `start-prod.sh` 即可。

---

## 🗄️ 数据库直连 (仅限开发环境)

为保证安全，生产环境默认切断了底层的端口映射。开发调试期间，如需直连排查数据，可使用以下配置：

**MongoDB 核心数据库**
* **直连 URI**: `mongodb://admin:admin@127.0.0.1:27018/arl?authSource=admin`
* **拆解参数**: 端口 `27018` | 账号/密码 `admin`/`admin` | 业务库 `arl` | 认证库 `admin`

**RabbitMQ 消息队列**
* **AMQP 通信端口**: `5673`
* **Web 管理后台**: `http://127.0.0.1:15673`
* **认证账号/密码**: `admin` / `admin`

---

## 📜 版本更新历史

<details>
<summary><b>v1.1.2 (当前版本)</b></summary><br/>

* **核心**：新增系统一键升级机制，支持平滑热更新。
* **组件**：Nuclei 扫描引擎升级至 v3.11.0。
* **前端**：极致性能优化，修复 Auth 拦截器等验证问题。
</details>

<details>
<summary><b>v1.1.1</b></summary><br/>

* **资产**：资产范围 (Scope) 扩充，全面支持并严格区分 Domain 与 IP 类型的目标校验与调度。
* **功能**：新增自定义 PoC 源码在线读取、编辑与全可视化创建管理，增强了级联删除逻辑。
* **功能**：新增字典配置模块，提供弱口令字典查询、预览及可视化读写管理。
* **优化**：360 搜索引擎采集逻辑新增反爬熔断保护，追加高价值关键字深度挖掘；生产环境 Nginx 开启 Gzip 压缩。
* **修复**：修复前端详情页高级搜索表单及组件数据联动异常。
</details>

<details>
<summary><b>v1.1.0</b></summary><br/>

* **新增**：全新引入 GitHub 威胁情报雷达（支持 CVE 漏洞雷达、安全武器库及黑客动态监测）。
* **新增**：完善告警生态，支持 Telegram 机器人推送告警。
* **重构**：前端系统设置与 Github 管理页面结构重构，全面启用 HTTP/2 多路复用，大幅降低前端并发加载延迟。
* **修复**：修复 HTTP 存活检测与站点截图组件在 Docker 下的超时和崩溃 Bug，及仪表盘漏洞趋势无数据的 Bug。
</details>

<details>
<summary><b>v1.0.9</b></summary><br/>

* **重构**：分离后端 ARL 内部漏洞与 Nuclei 引擎扫描结果的统计逻辑。
* **交互**：Dashboard 漏洞统计卡片 UI 极简重构，支持按漏洞类型与危害等级点击下钻（Drill-down）。
* **交互**：资产查询页面支持接收仪表盘的联动请求，实现页面跳转与高级筛选项的自动填充。
</details>

<details>
<summary><b>v1.0.8</b></summary><br/>

* **功能**：完善 POC 导入机制，支持批量拖拽上传验证脚本，并提供标准 Python POC 模板下载。
* **架构**：引入 Celery 任务并发热扩缩容机制，修改并发数配置后即时生效，无需重启服务。
* **重构**：重构仪表盘底层查询逻辑，统一基于站点表单库进行海量数据的高效查询。
* **部署**：深度分离开发与生产环境启动脚本，增加 POC 独立数据卷挂载。
* **优化**：优化前端站点截图预览样式防变形，并持续迭代系统内置指纹库。
</details>

---

## 🤝 致谢

本项目站在巨人的肩膀上，特此鸣谢以下项目与团队：

* **核心架构**：基于原版 [ARL 灯塔](https://github.com/TophantTechnology/ARL) 重构，同时参考了优秀衍生版 [Aabyss-Team/ARL](https://github.com/Aabyss-Team/ARL) 与 [adysec/ARL](https://github.com/adysec/ARL)。
* **指纹数据**：感谢 **威零安全团队** (<img src="img/weiling.jpg" width="18" height="18" align="absmiddle" /> 公众号) 提供的 16,985 条高质量指纹。
* **功能模块**：
  * **企业查询**：基于 [ICP_Query](https://github.com/HG-ha/ICP_Query) 二次开发。
  * **CVE 监控**：借鉴自 [github-cve-monitor](https://github.com/yhy0/github-cve-monitor)。

ARL-Next 将秉持开源互助的初心，持续为信息安全社区贡献力量！

---

## ⚠️ 声明与免责

本工具仅面向合法授权的企业安全建设、SRC 漏洞挖掘以及安全研究学术交流。
使用本工具进行资产扫描与漏洞探测时，请务必遵守当地法律法规（如《中华人民共和国网络安全法》）及目标平台的测试范围规定。未经授权对目标进行探测属非法行为。使用者因使用本工具造成的任何直接或间接的法律责任与后果，由使用者自行承担，项目作者及贡献者不负任何连带责任。

---

## 💬 问题反馈与交流

在使用过程中如遇到 Bug、有新的功能建议，或是想探讨安全开发与红蓝对抗技术，欢迎通过 GitHub Issues 提交反馈。

同时也欢迎通过以下方式与我联系交流：

<table align="center">
  <tr>
    <td align="center" style="padding: 0 60px;"><b>个人微信</b></td>
    <td align="center" style="padding: 0 60px;"><b>QQ交流群</b></td>
  </tr>
  <tr>
    <td align="center" style="padding: 0 60px;"><img src="./img/wechat.png" alt="个人微信" height="525" /></td>
    <td align="center" style="padding: 0 60px;"><img src="./img/qq_group.jpg" alt="QQ交流群" height="525" /></td>
  </tr>
</table>


---

## 🌟 Star History

**⭐ 如果本项目为你的安全工作带来了便利，不妨点个 Star 支持一下！**

<div align="center">

<a href="https://www.star-history.com/?repos=owl234%2Farl-next&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&theme=dark&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
 </picture>
</a>

</div>


