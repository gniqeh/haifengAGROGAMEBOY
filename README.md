# AGRO GAMEBOY

面向会议现场 1920×1080 触摸屏的农业经营模拟互动。不是答题器：每个终端独立接管一块虚拟农田，自行完成巡田、资源配置、AI 协同、突发事件处置和经营结果模拟。

## Debian + mamba 快速启动

```bash
git clone https://github.com/gniqeh/haifengAGROGAMEBOY.git
cd haifengAGROGAMEBOY

mamba create -n agrogameboy python=3.11 -y
mamba activate agrogameboy
pip install -r requirements.txt

PORT=8831 bash start.sh
```

参与端：`http://服务器IP:8831/`

观察后台：`http://服务器IP:8831/admin`

`start.sh` 会优先使用项目 `.venv`，不存在时直接使用当前已激活的 mamba/conda 环境。

## 互动流程

1. **巡田**：点击四个田区，比较土壤水分、NDVI、风险和长势。
2. **资源配置**：有限水肥资源由参与者自行分配到各田区，资源总量受到约束。
3. **AI 协同**：展示参与者方案和 AI 方案差异，参与者决定保留、采用或参考调整。
4. **突发事件**：天气、病害或低温事件出现，参与者选择处置方式。
5. **经营结果**：根据资源配置和事件处理计算模拟产量、收益、资源效率、风险指数与综合经营分。

每个浏览器使用本地 UUID 区分，同时记录 IP。参与者按自己的节奏推进，不需要主持人逐步控制。

## 后台

`/admin` 只承担现场观察和必要的重置：

- 在线终端数
- 已登记终端数
- 已完成数量
- 每个终端当前阶段
- 最终经营分和收益
- 全场平均经营分和收益
- 一键重置本场

## 场景配置

农业情境在 `scenarios.json`。当前包含玉米、大豆、水稻 3 套场景。可以继续增加场景，每套定义：田区状态、可用资源、AI 推荐配置、突发事件、事件动作评分、基础产量价格等。

## 数据

SQLite 文件为 `agrogameboy.db`，运行时自动创建。无需 Redis、PostgreSQL 或 Docker。十来块会议触摸屏没必要举行基础设施阅兵式。
