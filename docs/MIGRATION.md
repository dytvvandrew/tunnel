# 一键迁移方案

## 迁移边界

GitHub 仓库只同步代码和部署脚本，不同步以下内容：

- `.env` 和 API Key
- `platform/app.db`
- `platform/uploaded_tunnels.json`
- `structured/`、`raw/`、`models/`、`uploads/`
- `rag/raw/`、`rag/processed/`、`rag/chunks/`、`rag/indexes/`、`rag/metadata/`
- Qwen 模型权重

这些运行时资产使用 `scripts/package_runtime.sh` 打成迁移包。

## 旧服务器打包

在旧服务器项目根目录执行：

```bash
bash scripts/package_runtime.sh
```

生成文件类似：

```text
runtime_backups/tunnel_runtime_20260716_153000.tar.gz
```

把这个压缩包复制到新服务器同一项目目录的 `runtime_backups/` 下。

## 新服务器恢复

```bash
git clone <your-github-repo-url> tunnel-platform
cd tunnel-platform
cp .env.example .env
bash scripts/install_ubuntu.sh
bash scripts/restore_runtime.sh runtime_backups/tunnel_runtime_20260716_153000.tar.gz
bash scripts/start_platform.sh
```

`.env.example` 默认给出演示账号：

```bash
ADMIN_USERNAME=123
ADMIN_PASSWORD=123456
```

正式部署时建议改成更强密码。

## systemd 托管

编辑 `deploy/tunnel-platform.service` 中的路径和用户，然后：

```bash
sudo cp deploy/tunnel-platform.service /etc/systemd/system/tunnel-platform.service
sudo systemctl daemon-reload
sudo systemctl enable --now tunnel-platform
sudo systemctl status tunnel-platform
```

## 本地 Qwen

Qwen 权重不建议进入本仓库。新服务器上单独部署 vLLM，然后在 `.env` 中配置：

```bash
BRAIN_PROVIDER=local-vllm
BRAIN_API_BASE=http://127.0.0.1:18021/v1
BRAIN_MODEL=qwen2.5-7b
BRAIN_API_KEY=
```
