# 临时展位三相配电排布 API

为临时展位的三相（A / B / C）配电提供设备接入方案计算服务。

- 每台设备**不可拆分**，只能接入其允许相位集合中的一个相位；
- 在所有设备均接入、且各相负载不超过容量的前提下，
  **最小化三相负载最大值与最小值之差**；
- 差值相同时，取**按设备编号排序后的相位序列字典序最小**的方案；
- 不存在可行方案时返回明确的 `feasible: false` 结果；
- 每次计算的输入、分配结果与各相负载均落库保存，可随时查询。

技术栈：Python 3.12 · FastAPI · SQLite（标准库 `sqlite3`）· Uvicorn · Docker Compose。

## 一条命令启动

```bash
docker compose up --build -d
```

启动时会自动完成：安装依赖 → 构建镜像 → 启动服务 → **自动创建并初始化 SQLite 数据库表**（应用 FastAPI lifespan 中幂等执行，无需任何手工迁移）。

停止：

```bash
docker compose down          # 保留数据
docker compose down -v       # 同时删除数据库卷
```

## 访问地址与端口

| 用途 | 地址 |
| --- | --- |
| API 根路径 | http://localhost:8000/ |
| 健康检查 | http://localhost:8000/health |
| Swagger 交互文档 | http://localhost:8000/docs |
| OpenAPI 描述 | http://localhost:8000/openapi.json |

## 必要配置

所有配置均有默认值，零配置即可启动：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HOST_PORT` | `8000` | 宿主机映射端口（如端口被占用：`HOST_PORT=9000 docker compose up --build -d`） |
| `DB_PATH` | `/data/phase_allocations.db` | 容器内 SQLite 文件路径，位于命名卷 `phase-db-data` 中，容器重建数据不丢 |
| `UVICORN_HOST` / `UVICORN_PORT` | `0.0.0.0` / `8000` | 容器内监听地址与端口 |

## API

### `POST /api/allocations` — 计算并保存一个分配方案

请求体：

- `devices`：1～12 台设备；
  - `id`：设备唯一编号（非空字符串，同一请求内不可重复）；
  - `power`：功率，**正整数**（瓦）；
  - `allowed_phases`：**非空**可接入相位集合，元素取值 `A` / `B` / `C`；
- `capacities`：A/B/C 各相容量（非负整数，瓦）。

```bash
curl -s http://localhost:8000/api/allocations \
  -H 'Content-Type: application/json' \
  -d '{
    "devices": [
      {"id": "light-01", "power": 3000, "allowed_phases": ["A", "B", "C"]},
      {"id": "screen-01", "power": 5000, "allowed_phases": ["A", "B"]},
      {"id": "fridge-01", "power": 2000, "allowed_phases": ["C"]},
      {"id": "socket-01", "power": 1500, "allowed_phases": ["A", "B", "C"]}
    ],
    "capacities": {"A": 6000, "B": 6000, "C": 6000}
  }'
```

可行时响应（HTTP 201）：

```json
{
  "id": 1,
  "created_at": "2026-09-24T13:58:06.473Z",
  "feasible": true,
  "devices": [ ... 原样保存的输入设备 ... ],
  "capacities": {"A": 6000, "B": 6000, "C": 6000},
  "assignments": [
    {"id": "fridge-01", "phase": "C"},
    {"id": "light-01", "phase": "A"},
    {"id": "screen-01", "phase": "B"},
    {"id": "socket-01", "phase": "C"}
  ],
  "phase_loads": {"A": 3000, "B": 5000, "C": 3500},
  "load_diff": 2000,
  "message": null
}
```

说明：`assignments` 始终按设备编号升序排列；同极差下保证该相位序列在所有最优解中字典序最小（相位顺序 `A < B < C`）。

**无可行分配**时（如总容量不足、某设备所有允许相位均超载、相位限制导致组合冲突）：

```json
{
  "id": 2,
  "created_at": "...",
  "feasible": false,
  "devices": [ ... ],
  "capacities": { ... },
  "assignments": null,
  "phase_loads": null,
  "load_diff": null,
  "message": "不存在满足各相容量约束的可行分配方案"
}
```

无可行方案同样保存记录并返回 HTTP 201；输入本身非法（编号重复/为空、功率非正整数、相位集合为空、设备数超 12 等）返回 HTTP 422 及校验错误明细。

### `GET /api/allocations` — 历史计算列表（不含明细）

```bash
curl -s 'http://localhost:8000/api/allocations?limit=20&offset=0'
```

按记录 ID 倒序返回，支持分页：`limit`（1～200，默认 50）、`offset`（默认 0）。

### `GET /api/allocations/{id}` — 查询单条计算的完整记录

```bash
curl -s http://localhost:8000/api/allocations/1
```

返回该次计算的输入设备、容量、分配结果与各相负载；记录不存在返回 HTTP 404。

## 本地开发（不用 Docker）

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DB_PATH=./phase_allocations.db uvicorn app.main:app --reload
```

## 测试

求解器为纯标准库实现，可直接运行（无需安装依赖）：

```bash
python3 tests/test_solver.py
```

该测试用穷举全部相位组合的参考实现做交叉验证，并覆盖：极差优先、字典序平局裁决、相位受限、容量约束、不可行场景与 12 台设备的性能上限（3^12 个叶节点，毫秒级）。

## 项目结构

```
.
├── app/
│   ├── __init__.py
│   ├── main.py        # FastAPI 路由与启动建表
│   ├── schemas.py     # 请求/响应模型与输入校验
│   ├── solver.py      # 三相均衡求解器（DFS 穷举 + 容量剪枝）
│   └── database.py    # SQLite 初始化与持久化
├── tests/
│   └── test_solver.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
