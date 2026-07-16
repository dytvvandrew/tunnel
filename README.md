# Tunnel Smart Control Platform

隧道智慧管控平台的一键迁移版工程目录。

本仓库只保存代码、脚本、配置模板和说明文档。工程数据、PDF 原件、三维模型、上传文件、RAG 原文与索引、数据库和模型权重都不进入 GitHub；这些内容通过运行时迁移包单独备份和恢复。

## 目录

```text
build_control_platform.py      # 生成 platform/index.html 和前端数据
tunnel_login_app.py            # 登录、上传建模、智慧大脑 API 服务
rag/                           # RAG 检索代码与配置
scripts/                       # 安装、启动、备份、恢复、健康检查脚本
deploy/                        # systemd 服务模板
docs/                          # 迁移和 RAG 架构说明
structured/ raw/ models/       # 运行时数据目录，Git 只保留 .gitkeep
uploads/ platform/             # 上传数据、生成页面和本地数据库目录
```

## 快速启动

```bash
cp .env.example .env
bash scripts/install_ubuntu.sh
bash scripts/start_platform.sh
```

如果是从旧服务器迁移，需要先恢复运行时包：

```bash
bash scripts/restore_runtime.sh runtime_backups/tunnel_runtime_YYYYmmdd_HHMMSS.tar.gz
bash scripts/start_platform.sh
```

`.env.example` 中默认演示账号为 `123 / 123456`。正式部署时请改强密码。

默认访问地址：

```text
http://服务器IP:8010/platform/index.html
```

## API Key 与 RAG

可以购买商业 API Key，也可以使用本地 Qwen/vLLM。RAG 仍然可以挂载，因为 RAG 是平台自己的检索层：平台先从本地知识库检索资料，再把检索结果与当前隧道数据一起发送给模型接口。

详见 [docs/RAG_WITH_API_KEY.md](docs/RAG_WITH_API_KEY.md)。

GitHub 推送流程见 [docs/GITHUB_SYNC.md](docs/GITHUB_SYNC.md)。
