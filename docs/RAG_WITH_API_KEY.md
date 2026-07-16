# API Key 接入时是否还能挂载 RAG

可以。

RAG 不依赖某一个大模型供应商，它是平台后端自己的检索流程。完整链路是：

```text
用户问题
  -> 平台读取当前隧道实时数据
  -> 本地 RAG 检索工程资料、规范、教材、项目文档
  -> 拼接成 prompt 上下文
  -> 调用本地 Qwen 或商业 API
  -> 返回答案和资料来源
```

因此，购买 API Key 后只需要把 `.env` 改成商业 API 的 OpenAI-compatible 地址：

```bash
BRAIN_PROVIDER=commercial-api
BRAIN_API_BASE=https://api.example.com/v1
BRAIN_MODEL=your-chat-model
BRAIN_API_KEY=sk-xxxxxxxx
BRAIN_RAG_ENABLED=1
```

## 推荐架构

第一阶段建议采用“本地 RAG + 外部 API 推理”：

- RAG 索引、项目资料、施工数据仍放在本地服务器。
- 只把检索后的少量文本片段发给 API。
- 不上传完整教材、PDF、点云、模型文件。
- 答案中保留资料来源，便于汇报和追溯。

如果甲方对资料安全要求更高，就继续使用“本地 RAG + 本地 Qwen”。

## 注意

商业 API 的上下文窗口、价格、速率限制和数据合规策略不同，需要按供应商确认。平台侧只要求接口兼容 `/v1/chat/completions`。

