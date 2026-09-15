# haifengAGROGAMEBOY

面向会议现场触摸屏的农业互动系统。参与者无需登录和键盘，浏览器打开页面即可参与；主持人通过后台统一控制轮次、公布结果和查看实时统计。

## Debian 快速部署

```bash
git clone https://github.com/gniqeh/haifengAGROGAMEBOY.git
cd haifengAGROGAMEBOY
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash start.sh
```

默认监听 `0.0.0.0:8830`。

参与端：`http://服务器IP:8830/`

主持后台：`http://服务器IP:8830/admin`

如需改端口：

```bash
PORT=8835 bash start.sh
```

可使用 8830~8839 中任意空闲端口。

如果 Debian 提示无法创建 venv：

```bash
sudo apt update
sudo apt install -y python3-venv
```

## 功能

- 触摸屏友好的大按钮参与端
- 浏览器本地设备 ID + IP 双重记录终端
- 普通 HTTP 局域网环境可用，不依赖 HTTPS 才能生成设备编号
- SQLite 自动建库，无需额外数据库
- WebSocket 实时同步主持人控制与参与端状态
- 主持后台查看在线终端、答题进度和实时统计
- 开始、上一题、下一题、公布/隐藏结果、结束、全量重置
- 同一终端在当前轮次可修改选择
- `questions.json` 独立配置互动内容

## 修改题目

编辑 `questions.json` 后重启服务即可。每题包含标题、说明、选项以及可选的 AI 建议和解释。

## systemd（可选）

若需要开机自启，可自行将 `start.sh` 配置为 systemd 服务。第一版刻意不引入 Docker、Redis、PostgreSQL 等大型仪式用品，因为十几块触摸屏并不值得召开一场基础设施峰会。
