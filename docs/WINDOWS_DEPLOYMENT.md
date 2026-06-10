# Windows 部署与启动指南

本文档面向在 Windows 本机、PowerShell、Git Bash 或 WSL 中运行 DeerFlow 的场景。DeerFlow 是多进程应用，推荐始终通过统一入口访问，而不是直接打开前端端口 `http://localhost:3000`。

本机访问时使用：

```text
http://localhost:2026
```

远程访问时使用 Windows 主机的 IP 或域名：

```text
http://<Windows主机IP>:2026
http://<你的域名>:2026
```

## 1. 运行结构

标准开发模式包含 4 个服务：

| 服务 | 默认端口 | 作用 |
| --- | --- | --- |
| LangGraph | `2024` | 智能体运行时、线程状态、流式输出 |
| Gateway | `8001` | REST API、模型、MCP、技能、上传、管理接口 |
| Frontend | `3000` | Next.js 前端 |
| nginx | `2026` | 统一入口和 API 反向代理 |

nginx 路由规则：

| 浏览器请求 | 代理目标 |
| --- | --- |
| `/api/langgraph/*` | `http://127.0.0.1:2024/*` |
| `/api/*` | `http://127.0.0.1:8001/api/*` |
| `/` | `http://127.0.0.1:3000/` |

因此正常访问地址是：

```text
http://localhost:2026
```

如果从其他电脑或公网访问，把 `localhost` 换成部署 DeerFlow 的 Windows 主机 IP 或域名：

```text
http://192.168.1.10:2026
http://deerflow.example.com:2026
```

## 2. 前置要求

Windows 环境需要安装：

- Node.js 22+
- pnpm 10.26.2+
- Python 3.12+
- uv
- Git Bash
- nginx

检查命令：

```powershell
make check
```

首次启动前：

```powershell
make config
make install
```

如果 `config.yaml` 已经存在，`make config` 会中止，这是正常行为。

## 3. 推荐启动方式

在项目根目录运行：

```powershell
make dev
```

Windows 下 `Makefile` 会通过 `scripts\run-with-git-bash.cmd` 调用 `scripts/serve.sh`，并启动 LangGraph、Gateway、Frontend、nginx。启动完成后访问：

```text
http://localhost:2026
```

远程访问时访问：

```text
http://<Windows主机IP>:2026
```

停止服务：

```powershell
make stop
```

## 4. 手动逐个启动

如果你需要一个一个启动服务，也必须把 nginx 启动起来，并从 `2026` 端口访问。

### 终端 1：LangGraph

```powershell
cd backend
make dev
```

确认端口：

```text
http://localhost:2024
```

### 终端 2：Gateway

```powershell
cd backend
make gateway
```

确认健康检查：

```text
http://localhost:8001/health
```

### 终端 3：Frontend

```powershell
cd frontend
pnpm dev
```

前端服务端口是：

```text
http://localhost:3000
```

不要把这个地址作为主访问入口，除非你非常确认 API 代理配置正确。

### 终端 4：nginx

在项目根目录启动 nginx：

```powershell
nginx -g "daemon off;" -c "%cd%\docker\nginx\nginx.local.conf" -p "%cd%"
```

如果在 Git Bash 中运行：

```bash
nginx -g "daemon off;" -c "$(pwd)/docker/nginx/nginx.local.conf" -p "$(pwd)"
```

最终访问：

```text
http://localhost:2026
```

远程访问时访问：

```text
http://<Windows主机IP>:2026
```

## 5. 远程访问配置

如果你会从其他电脑、手机、内网机器或公网访问 Windows 上的 DeerFlow，需要额外确认网络入口。

### 5.1 确认 Windows 主机 IP

在 Windows PowerShell 中运行：

```powershell
ipconfig
```

找到当前网卡的 IPv4 地址，例如：

```text
192.168.1.10
```

同一内网中的其他设备访问：

```text
http://192.168.1.10:2026
```

### 5.2 放行 Windows 防火墙

只需要对外放行 nginx 统一入口端口 `2026`。

PowerShell 以管理员身份运行：

```powershell
New-NetFirewallRule `
  -DisplayName "DeerFlow nginx 2026" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 2026 `
  -Action Allow
```

不建议对远程访问暴露这些端口：

```text
2024  LangGraph
8001  Gateway
3000  Frontend
```

这些服务应只作为 nginx 的本机上游，由 `2026` 统一入口转发。

### 5.3 云服务器安全组

如果 Windows 部署在云服务器上，还需要在云厂商控制台放行入站 TCP `2026`。

公网访问地址通常是：

```text
http://<公网IP>:2026
```

如果绑定域名：

```text
http://<你的域名>:2026
```

生产或公网长期使用时，建议再加一层标准反向代理和 HTTPS，将外部 `443` 转发到本机 `2026`。

### 5.4 不要把远程浏览器写成 localhost

远程电脑上的：

```text
http://localhost:2026
```

指的是远程电脑自己，不是部署 DeerFlow 的 Windows 主机。

必须使用：

```text
http://<Windows主机IP>:2026
```

或者：

```text
http://<你的域名>:2026
```

## 6. 直接访问 3000 的注意事项

前端代码默认会按当前浏览器来源拼出 API 地址：

- LangGraph 默认：`/api/langgraph`
- Gateway 默认：`/api/...`

在 `http://localhost:2026` 下，这些请求由 nginx 正确转发。

在 `http://localhost:3000` 下，Next.js 会尝试使用 `next.config.js` 中的 rewrite 转发到：

```text
http://127.0.0.1:2024
http://127.0.0.1:8001
```

Windows、WSL、Docker 混合运行时，`127.0.0.1` 可能指向的是不同网络命名空间。例如：

- 前端跑在 Windows，本地后端跑在 WSL
- 前端跑在 WSL，后端跑在 Windows
- 前端跑在容器，后端跑在宿主机

这种情况下，直接打开 `3000` 很容易出现主界面一直加载、模型列表为空、聊天无法开始等问题。

如果必须直接访问 `3000`，优先使用服务端内部地址变量，而不是 `NEXT_PUBLIC_*`：

```powershell
$env:DEER_FLOW_INTERNAL_LANGGRAPH_BASE_URL="http://127.0.0.1:2024"
$env:DEER_FLOW_INTERNAL_GATEWAY_BASE_URL="http://127.0.0.1:8001"
cd frontend
pnpm dev
```

如果后端不在同一个网络命名空间，把上面的地址换成前端进程能访问到的实际地址。

## 7. 环境变量注意事项

不推荐在普通本地开发中设置：

```env
NEXT_PUBLIC_BACKEND_BASE_URL=http://localhost:8001
NEXT_PUBLIC_LANGGRAPH_BASE_URL=http://localhost:2024
```

原因：

1. 设置 `NEXT_PUBLIC_LANGGRAPH_BASE_URL` 后，前端会直接访问该地址，不再走默认 `/api/langgraph`。
2. 设置 `NEXT_PUBLIC_BACKEND_BASE_URL` 后，Next.js 中 `/api/*` 的 rewrite 会被关闭。
3. 如果浏览器和后端之间存在跨域、Cookie 或 Windows/WSL 网络差异，请求会更容易失败。

推荐做法：

- 使用 `make dev`，访问 `http://localhost:2026`
- 或手动启动 nginx，仍然访问 `http://localhost:2026`
- 只有在清楚网络拓扑时，才设置 `DEER_FLOW_INTERNAL_LANGGRAPH_BASE_URL` 和 `DEER_FLOW_INTERNAL_GATEWAY_BASE_URL`

远程访问时也不要把 `NEXT_PUBLIC_BACKEND_BASE_URL` 或 `NEXT_PUBLIC_LANGGRAPH_BASE_URL` 设置成远程访问地址。浏览器只需要访问 nginx 入口，前端请求保持 `/api/...` 相对路径即可。

## 8. 主界面一直加载的排查

如果登录后进入主界面一直显示加载中或页面不变化，按下面顺序检查。

### 8.1 确认访问入口

本机访问时，优先确认浏览器地址栏是：

```text
http://localhost:2026
```

远程访问时，确认浏览器地址栏是部署机器的 IP 或域名：

```text
http://<Windows主机IP>:2026
http://<你的域名>:2026
```

如果是：

```text
http://localhost:3000
```

先切换到 `2026` 再试。

### 8.2 检查 4 个端口

```powershell
netstat -ano | findstr ":2024"
netstat -ano | findstr ":8001"
netstat -ano | findstr ":3000"
netstat -ano | findstr ":2026"
```

四个端口都应该处于监听状态。

### 8.3 检查 Gateway

在 Windows 主机本机浏览器打开：

```text
http://localhost:2026/health
```

远程机器打开：

```text
http://<Windows主机IP>:2026/health
```

如果失败，说明 nginx 到 Gateway 的代理或 Gateway 服务有问题。

### 8.4 检查前端 API 请求

打开浏览器开发者工具的 Network 面板，重点看：

```text
/api/models
/api/threads/search
/api/langgraph/threads
/api/langgraph/threads/.../state
```

常见现象：

| 现象 | 可能原因 |
| --- | --- |
| 请求一直 pending | 后端端口不可达，或 Windows/WSL 地址不通 |
| `404` | 请求打到了 Frontend，而不是 Gateway/LangGraph |
| `502` / `504` | nginx 找不到上游服务 |
| `401` | 登录态失效或 Gateway 认证失败 |
| CORS 错误 | 绕过了 nginx，浏览器直接跨域访问后端 |

远程访问时，如果本机 `http://localhost:2026/health` 正常，但远程 `http://<Windows主机IP>:2026/health` 失败，优先检查 Windows 防火墙、云安全组、路由器端口转发或服务器公网网络策略。

### 8.5 检查日志

使用 `make dev` 或 `scripts/serve.sh` 启动时，日志在：

```text
logs/langgraph.log
logs/gateway.log
logs/frontend.log
logs/nginx.log
logs/nginx-error.log
```

重点先看 `nginx-error.log` 和 `gateway.log`。

## 9. Windows / WSL 网络建议

为了减少 `localhost` 指向不一致的问题，建议同一套服务尽量运行在同一个环境中：

- 全部运行在 Windows 原生环境
- 或全部运行在 WSL 中
- 或全部运行在 Docker Compose 中

不推荐混合方式：

- Frontend 在 Windows，Backend 在 WSL
- Frontend 在 WSL，Backend 在 Windows
- Frontend 在容器，Backend 在宿主机

如果必须混合运行，请明确每个进程能访问到的后端地址，并使用 `DEER_FLOW_INTERNAL_LANGGRAPH_BASE_URL`、`DEER_FLOW_INTERNAL_GATEWAY_BASE_URL` 指向这些地址。

## 10. 快速结论

Windows 下最稳妥的启动方式：

```powershell
make dev
```

最稳妥的访问地址：

```text
http://localhost:2026
```

远程访问地址：

```text
http://<Windows主机IP>:2026
```

远程访问只需要放行：

```text
TCP 2026
```

如果手动逐个启动，必须同时启动：

```text
LangGraph 2024
Gateway 8001
Frontend 3000
nginx 2026
```

主界面卡在加载中时，优先检查是否误访问了 `http://localhost:3000`，以及 `/api/langgraph/*`、`/api/models`、`/api/threads/search` 是否正确转发到了后端。
