# haifengAGROGAMEBOY

农业知识答题闯关，FastAPI + SQLite，可直接部署在 Debian 内网服务器。

## 启动

```bash
pip install -r requirements.txt
python app.py
```

默认监听 `0.0.0.0:8831`。自定义端口：

```bash
python app.py --port 8835
```

也可同时指定监听地址：`python app.py --host 0.0.0.0 --port 8835`。

- 答题页：`http://服务器IP:8831/`
- 统计后台：`http://服务器IP:8831/admin`
- 后台密码：`hfgdmm`

后台使用 SQLite 文件 `quiz_results.db` 持久保存答题时间、客户端 IP、得分、正确率、等级、逐题作答和 User-Agent，并支持 CSV 导出。

> 如果前面使用 Nginx/反向代理，请正确传递 `X-Real-IP` 或 `X-Forwarded-For`，否则后台看到的可能是代理服务器 IP。
