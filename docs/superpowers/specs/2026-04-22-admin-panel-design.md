# DeerFlow 管理端设计文档

## 概述

为 DeerFlow 新增管理端系统，包含用户管理、部门管理和 Skill 管理三大模块。支持 RBAC 权限控制、Skill 审核流程和多级可见性控制。

### 技术选型

| 维度 | 选择 |
|------|------|
| 前端 | React + Vite + Tailwind + Ant Design（独立 SPA） |
| 后端 | 集成到现有 Gateway（`/api/admin/*`） |
| ORM | SQLAlchemy 2.0 async |
| 数据库 | PostgreSQL |
| 文件存储 | MinIO |
| 认证 | JWT（access_token + refresh_token） |
| 部署 | 复用现有 nginx 代理 |
| 部署场景 | 单租户优先，预留多租户 |

### 角色体系

| 角色 | 权限范围 |
|------|----------|
| `super_admin` | 所有操作：用户/部门/Skill 的增删改查、Skill 审核。可有多个 |
| `dept_admin` | 管理本部门用户（增删改查）、管理本部门 Skill、发布部门 Skill |
| `user` | 上传/管理自己的 Skill，查看有权限的 Skill |

## 1. 数据库模型

### 1.1 departments 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID (PK) | 主键 |
| name | VARCHAR(100) | 部门名称 |
| parent_id | UUID (FK, nullable) | 上级部门，自引用，支持多级树形结构 |
| tenant_id | VARCHAR(50) | 多租户预留，默认 `'default'` |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 1.2 users 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID (PK) | 主键 |
| username | VARCHAR(50) (UNIQUE) | 登录用户名 |
| password_hash | VARCHAR(255) | bcrypt 密码哈希 |
| display_name | VARCHAR(100) | 显示名称 |
| email | VARCHAR(255) | 邮箱 |
| department_id | UUID (FK → departments) | 所属部门 |
| role | ENUM(super_admin, dept_admin, user) | 角色 |
| status | ENUM(active, disabled) | 账号状态 |
| tenant_id | VARCHAR(50) | 多租户预留，默认 `'default'` |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 1.3 skills 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID (PK) | 主键 |
| name | VARCHAR(100) (UNIQUE) | Skill 名称 |
| description | TEXT | 描述 |
| version | VARCHAR(20) | 版本号 |
| author_id | UUID (FK → users) | 上传者 |
| department_id | UUID (FK, nullable) | 所属部门 |
| visibility | ENUM(company, department, specific_users, private) | 可见性级别 |
| status | ENUM(pending_review, approved, rejected, withdrawn) | 审核状态 |
| minio_bucket | VARCHAR(100) | MinIO 桶名 |
| minio_object_key | VARCHAR(500) | MinIO 对象路径 |
| file_size | BIGINT | 文件大小（字节） |
| reviewed_by | UUID (FK → users, nullable) | 审核人 |
| reviewed_at | TIMESTAMP (nullable) | 审核时间 |
| review_comment | TEXT (nullable) | 审核意见 |
| tenant_id | VARCHAR(50) | 多租户预留 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 1.4 skill_visible_users 关联表

仅 `visibility=specific_users` 时使用。

| 字段 | 类型 | 说明 |
|------|------|------|
| skill_id | UUID (FK → skills) | |
| user_id | UUID (FK → users) | |
| PK | (skill_id, user_id) | 联合主键 |

### 1.5 Skill 审核流程

```
用户上传 → pending_review（待审核）
                │
                ├─ super_admin 审核 → approved（通过，可设置可见性）
                │
                ├─ super_admin 驳回 → rejected（附 review_comment）
                │
                └─ 用户撤回 → withdrawn（可编辑后重新提交）
```

只有 `approved` 状态的 Skill 才会参与可见性判断和被智能体加载。

### 1.6 Skill 可见性规则

| 可见性 | 谁可以看到 |
|--------|-----------|
| `company` | 所有用户 |
| `department` | 同部门用户 |
| `specific_users` | `skill_visible_users` 表中匹配的用户 |
| `private` | 仅作者 |

### 1.7 多租户预留

所有表包含 `tenant_id` 字段，初期默认值为 `'default'`。查询时自动附加 `WHERE tenant_id = :current_tenant` 条件，通过 SQLAlchemy 的 tenant filter 实现。后续多租户支持时仅需实现租户识别逻辑（从 JWT 或域名提取）。

## 2. 后端架构

### 2.1 新增目录结构

在 `backend/app/` 下新增 `admin/` 模块：

```
app/
├── admin/                          ← 新增管理端模块
│   ├── __init__.py
│   ├── auth/
│   │   ├── jwt.py                  ← JWT 签发/验证/刷新
│   │   ├── password.py             ← bcrypt 密码哈希与验证
│   │   └── middleware.py           ← FastAPI 认证依赖注入
│   ├── models/
│   │   ├── base.py                 ← Base, TimestampMixin, TenantMixin
│   │   ├── user.py                 ← User ORM 模型
│   │   ├── department.py           ← Department ORM 模型
│   │   └── skill.py                ← Skill + SkillVisibleUser ORM 模型
│   ├── schemas/
│   │   ├── auth.py                 ← LoginRequest, TokenResponse, UserInfo
│   │   ├── user.py                 ← UserCreate, UserUpdate, UserResponse, UserListResponse
│   │   ├── department.py           ← DepartmentCreate, DepartmentUpdate, DepartmentTreeResponse
│   │   └── skill.py                ← SkillUpload, SkillUpdate, SkillResponse, ReviewRequest
│   ├── routers/
│   │   ├── auth.py                 ← 登录/登出/刷新/个人信息
│   │   ├── users.py                ← 用户 CRUD
│   │   ├── departments.py          ← 部门 CRUD
│   │   └── skills.py               ← Skill 上传/审核/发布/查询/下载
│   ├── services/
│   │   ├── user_service.py         ← 用户业务逻辑
│   │   ├── department_service.py   ← 部门业务逻辑
│   │   └── skill_service.py        ← Skill 业务逻辑（含 MinIO 交互）
│   ├── deps.py                     ← get_db, get_current_user, require_role
│   └── minio.py                    ← MinIO client 单例
├── gateway/                        ← 现有 Gateway（不动）
│   ├── app.py                      ← 注册 admin routers
│   └── routers/
```

**依赖规则**：`app/admin/` 遵循与现有代码相同的边界 —— 可以导入 `deerflow.*`，但 `deerflow` 不能导入 `app.admin`。

### 2.2 API 设计

#### 认证 `/api/admin/auth`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/login` | 账号密码登录，返回 access_token + refresh_token | 公开 |
| POST | `/logout` | 登出（JWT 黑名单） | 已登录 |
| POST | `/refresh` | 用 refresh_token 换取新 access_token | 已登录 |
| GET | `/me` | 获取当前用户信息 | 已登录 |
| PUT | `/me/password` | 修改自己的密码 | 已登录 |

#### 用户管理 `/api/admin/users`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/` | 用户列表（分页、搜索、按部门筛选） | super_admin, dept_admin |
| POST | `/` | 创建用户 | super_admin, dept_admin（仅本部门） |
| GET | `/{id}` | 用户详情 | super_admin, dept_admin（本部门） |
| PUT | `/{id}` | 更新用户信息 | super_admin, dept_admin（本部门） |
| PUT | `/{id}/status` | 启用/禁用用户 | super_admin |
| DELETE | `/{id}` | 删除用户 | super_admin |

#### 部门管理 `/api/admin/departments`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/` | 部门树 | super_admin, dept_admin |
| POST | `/` | 创建部门 | super_admin |
| GET | `/{id}` | 部门详情（含成员列表） | super_admin, dept_admin（本部门） |
| PUT | `/{id}` | 更新部门 | super_admin |
| DELETE | `/{id}` | 删除部门（需先转移用户） | super_admin |

#### Skill 管理 `/api/admin/skills`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/` | Skill 列表（分页、按状态/部门/可见性筛选） | 已登录 |
| POST | `/` | 上传 Skill（→ pending_review） | 已登录 |
| GET | `/{id}` | Skill 详情 | 按可见性规则 |
| GET | `/{id}/download` | 下载 Skill 文件 | 按可见性规则 |
| PUT | `/{id}` | 更新 Skill 信息 | 作者本人 |
| PUT | `/{id}/visibility` | 设置可见性 | 作者（已 approved） |
| POST | `/{id}/submit` | 提交审核（withdrawn → pending_review） | 作者本人 |
| POST | `/{id}/withdraw` | 撤回（pending_review → withdrawn） | 作者本人 |
| POST | `/{id}/review` | 审核（approve/reject + comment） | super_admin |
| DELETE | `/{id}` | 删除 Skill | 作者本人 或 super_admin |

### 2.3 认证与权限机制

**JWT 流程**：
- 登录成功后签发 `access_token`（默认 60 分钟）和 `refresh_token`（默认 7 天）
- access_token 载荷包含：`user_id`, `username`, `role`, `department_id`, `tenant_id`
- refresh_token 仅包含 `user_id` 和 `token_type=refresh`，单独存储签名密钥以支持独立撤销

**依赖注入**（`deps.py`）：

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """从 app.state.db_engine 获取数据库会话"""

async def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)) -> User:
    """解析 JWT，查询用户，校验 status=active，返回 User ORM 对象"""

def require_role(*roles: UserRole):
    """返回 Depends 函数，检查当前用户角色是否在允许列表中"""
```

路由使用方式：

```python
@router.post("/api/admin/users")
async def create_user(
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
    ...
):
```

### 2.4 数据库连接与生命周期

- 在 `gateway/app.py` 的 `lifespan` 中初始化 SQLAlchemy `AsyncEngine`，存入 `app.state.db_engine`
- `get_db()` 通过 `AsyncSessionLocal` 提供请求级 session
- MinIO client 在 lifespan 中初始化为单例，存入 `app.state.minio_client`

### 2.5 配置文件扩展

`config.yaml` 新增 `admin` 段：

```yaml
admin:
  database_url: postgresql+asyncpg://user:pass@localhost:5432/deerflow_admin
  minio:
    endpoint: localhost:9000
    access_key: $MINIO_ACCESS_KEY
    secret_key: $MINIO_SECRET_KEY
    bucket: deerflow-skills
    secure: false
  jwt:
    secret_key: $JWT_SECRET_KEY
    access_token_expire_minutes: 60
    refresh_token_expire_days: 7
  initial_super_admin:
    username: admin
    password: $ADMIN_INITIAL_PASSWORD
    email: admin@example.com
```

`config.example.yaml` 同步更新，`config_version` 递增。通过 `make config-upgrade` 合并新字段。

### 2.6 MinIO 存储

**路径规则**：`skills/{department_id}/{skill_id}/{filename}`

- 部门级 Skill：`skills/{department_id}/{skill_id}/skill.zip`
- 无部门 Skill：`skills/global/{skill_id}/skill.zip`

**操作**：
- 上传：`put_object`，公开读或预签名 URL
- 下载：通过 `presigned_get_object` 生成临时下载链接（默认 1 小时有效）
- 删除：Skill 删除时同步清理 MinIO 对象

## 3. 前端架构

### 3.1 项目结构

在项目根目录新建 `admin/` 目录：

```
admin/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── index.html
├── public/
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   ├── client.ts              ← axios 实例 + JWT 拦截器（自动刷新 token）
    │   ├── auth.ts
    │   ├── users.ts
    │   ├── departments.ts
    │   └── skills.ts
    ├── hooks/
    │   ├── useAuth.ts
    │   └── useUsers.ts            ← TanStack Query hooks
    ├── layouts/
    │   └── AdminLayout.tsx        ← Ant Design ProLayout
    ├── pages/
    │   ├── login/
    │   │   └── LoginPage.tsx
    │   ├── dashboard/
    │   │   └── DashboardPage.tsx
    │   ├── users/
    │   │   ├── UserListPage.tsx
    │   │   └── UserFormModal.tsx
    │   ├── departments/
    │   │   ├── DepartmentPage.tsx
    │   │   └── DepartmentForm.tsx
    │   └── skills/
    │       ├── SkillListPage.tsx
    │       ├── SkillUploadModal.tsx
    │       └── SkillReviewModal.tsx
    ├── components/
    │   ├── AuthGuard.tsx           ← 路由权限守卫
    │   └── RoleGuard.tsx           ← 角色级别组件守卫
    ├── stores/
    │   └── auth.ts                 ← Zustand 认证状态
    └── types/
        └── index.ts
```

### 3.2 路由设计

| 路径 | 页面 | 权限 |
|------|------|------|
| `/login` | 登录页 | 公开 |
| `/admin/dashboard` | 仪表盘（统计概览） | 已登录 |
| `/admin/users` | 用户管理 | super_admin, dept_admin |
| `/admin/departments` | 部门管理 | super_admin |
| `/admin/skills` | Skill 管理 | 已登录（按角色区分操作） |
| `/admin/skills/review` | Skill 审核 | super_admin |

未登录访问 `/admin/*` 自动跳转 `/login`，登录成功后跳转 `/admin/dashboard`。

### 3.3 权限控制策略

**路由级别**：`AuthGuard` 组件包裹 `/admin/*` 路由，检查登录状态。

**菜单级别**：`AdminLayout` 侧边栏根据 `user.role` 动态渲染：
- `super_admin`：所有菜单
- `dept_admin`：用户管理（仅本部门）、Skill 管理
- `user`：仅 Skill 管理（自己的）

**组件级别**：`RoleGuard` 包裹操作按钮：

```tsx
<RoleGuard roles={[UserRole.SUPER_ADMIN]}>
  <Button onClick={handleReview}>审核</Button>
</RoleGuard>
```

### 3.4 核心页面交互

**登录页**：用户名 + 密码表单，登录成功后 JWT 存入 localStorage，跳转 dashboard。

**用户管理**：
- Ant Design ProTable，支持分页、搜索、部门筛选
- dept_admin 只能看到本部门用户，创建用户时部门自动锁定为本部门
- 新建/编辑通过 Modal 表单完成

**部门管理**：
- Ant Design Tree 组件，展示树形结构
- 支持新增/编辑/删除节点
- 删除部门前需确认转移该部门下的用户

**Skill 管理**：
- 标签页按状态分类：全部 / 待审核 / 已通过 / 已驳回 / 已撤回
- super_admin 可看所有；dept_admin 可看本部门；普通用户仅看自己的
- 上传弹窗支持文件拖拽，填写名称/描述/版本后提交，自动进入 `pending_review`
- 审核弹窗（仅 super_admin）显示 Skill 详情，选择通过/驳回并填写意见
- 可见性设置在 Skill approved 后可操作，`specific_users` 时弹出用户选择器

### 3.5 状态管理

- **认证状态**：Zustand store（`stores/auth.ts`），存储 token 和用户信息
- **页面刷新恢复**：从 localStorage 读取 token，调用 `/api/admin/auth/me` 验证并恢复用户状态
- **服务端数据**：TanStack Query 管理所有 API 数据，统一处理 loading/error/cache
- **JWT 刷新**：axios 响应拦截器捕获 401，自动尝试 refresh，失败则清除状态并跳转登录页

## 4. 部署集成

### 4.1 nginx 路由

```
现有路由（不变）：
  /api/langgraph/*  → LangGraph Server (2024)
  /api/*            → Gateway API (8001)
  /                 → Frontend (3000)

新增路由：
  /admin            → Admin SPA 静态资源
  /admin/*          → Admin SPA 静态资源（try_files 回退 index.html）
  /api/admin/*      → 已被 /api/* 规则覆盖，自动转发到 Gateway
```

### 4.2 Docker 集成

`docker/docker-compose-dev.yaml` 新增服务：

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: deerflow_admin
      POSTGRES_USER: deerflow
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
```

### 4.3 数据库迁移

使用 Alembic 管理 schema 版本：

```
backend/
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_admin_schema.py
└── alembic.ini
```

### 4.4 新增依赖

**后端** (`backend/pyproject.toml`)：

| 包 | 用途 |
|---|------|
| `sqlalchemy[asyncio]>=2.0` | ORM |
| `asyncpg>=0.30` | PostgreSQL async driver |
| `alembic>=1.14` | 数据库迁移 |
| `bcrypt>=4.0` | 密码哈希 |
| `PyJWT>=2.10` | JWT 签发与验证 |
| `minio>=7.2` | MinIO 客户端 |

**前端** (`admin/package.json`)：

| 包 | 用途 |
|---|------|
| `react`, `react-dom` | UI 框架 |
| `antd`, `@ant-design/icons` | UI 组件库 |
| `@ant-design/pro-components` | ProTable, ProLayout |
| `@tanstack/react-query` | 服务端状态管理 |
| `axios` | HTTP 客户端 |
| `zustand` | 客户端状态管理 |
| `react-router-dom` | 路由 |
| `tailwindcss` | CSS 工具类 |

### 4.5 Makefile 扩展

新增命令：

| 命令 | 说明 |
|------|------|
| `make admin-install` | 安装管理端前端依赖 |
| `make admin-dev` | 启动管理端前端开发服务器（port 3002） |
| `make admin-build` | 构建管理端前端生产版本 |
| `make db-migrate` | 执行数据库迁移 |
| `make db-seed` | 创建初始超级管理员 |

### 4.6 首次部署流程

1. 确保 PostgreSQL 和 MinIO 运行（`docker-compose` 或本地安装）
2. `make config` → 填写 `admin` 段配置（数据库 URL、MinIO 连接、JWT 密钥、初始管理员密码）
3. `make install` → 安装后端 + 前端 + 管理端依赖
4. `make db-migrate` → 创建数据库表
5. `make db-seed` → 创建初始超级管理员
6. `make dev` → 启动所有服务
7. 访问 `http://localhost:2026/admin` → 使用初始管理员账号登录

## 5. 安全考量

- **密码**：bcrypt 哈希，cost factor 12
- **JWT**：HS256 签名，access_token 短期（60 分钟），refresh_token 长期（7 天），独立密钥
- **JWT 黑名单**：登出时 refresh_token 加入 Redis/数据库黑名单（初期可用数据库表实现）
- **API 权限**：所有 `/api/admin/*` 路由（除 `/login`）均需 JWT 验证，操作级权限通过 `require_role` 检查
- **MinIO**：使用预签名 URL 下载，不直接暴露 MinIO 端口
- **SQL 注入**：SQLAlchemy ORM 参数化查询
- **XSS**：前端不渲染用户提交的 HTML，所有用户输入作为纯文本处理
