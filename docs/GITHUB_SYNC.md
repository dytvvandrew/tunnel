# GitHub 同步说明

本目录 `tunnel-platform/` 已经整理为可以单独上传 GitHub 的干净工程。

## 不会上传的内容

`.gitignore` 已排除运行时数据、模型、上传文件、RAG 原文和索引、`.env`、日志、本地数据库等内容。GitHub 上只保存代码、脚本、模板和文档。

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

## 本机当前限制

当前电脑没有安装 GitHub CLI `gh`，所以不能由我直接在本机创建 GitHub 仓库。可以安装 GitHub Desktop、GitHub CLI，或直接在网页新建仓库后用脚本推送。

