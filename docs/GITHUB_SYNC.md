# GitHub 同步说明

本目录 `tunnel-platform/` 已经整理为可以单独上传 GitHub 的干净工程。

## 不会上传的内容

`.gitignore` 已排除运行时数据、模型、上传文件、RAG 原文和索引、`.env`、日志、本地数据库等内容。GitHub 上只保存代码、脚本、模板和文档。

## GitHub Pages 网页

仓库包含 docs/index.html 静态公开演示和 .github/workflows/pages.yml 自动部署流程。推送到 main 后，GitHub Actions 会发布到：

    https://dytvvandrew.github.io/tunnel/

首次发布前，请在 GitHub 仓库的 Settings → Pages → Build and deployment 中将 Source 设为 GitHub Actions。以后修改 docs/ 或演示图片并推送，网页会自动更新。静态版不连接平台 API；身份认证、文件上传、自动建模和智慧大脑仍需要服务器完整功能版。

## 推送到已有 GitHub 仓库

在 Windows PowerShell 中执行：

```powershell
cd D:\guandao\tunnel-platform
.\scripts\git_publish.ps1 -RemoteUrl "https://github.com/你的用户名/你的仓库名.git"
```

如果使用 SSH：

```powershell
.\scripts\git_publish.ps1 -RemoteUrl "git@github.com:你的用户名/你的仓库名.git"
```

## 如果还没有 GitHub 仓库

先在 GitHub 网页上新建一个空仓库，不要勾选自动生成 README。然后复制仓库 URL，执行上面的 `git_publish.ps1`。

## 当前仓库

当前工程远程地址为 https://github.com/dytvvandrew/tunnel.git 。
