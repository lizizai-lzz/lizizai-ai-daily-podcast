# 技术解读播客模板

使用此模板将技术文档、API指南或开发者教程转换为播客。

## 输入准备

当用户想把技术内容转为播客时，帮助结构化输入：

1. **简化代码示例**：用自然语言描述替代代码片段
   - 不要展示实际代码，而是描述代码的功能
   - 聚焦概念而非语法

2. **移除复杂标记**：
   - 数学公式用文字解释
   - API端点按功能描述而非URL路径
   - 配置示例总结为设置说明

3. **添加上下文**：
   - 解释为什么这项技术很重要
   - 包含实际应用场景
   - 为复杂概念添加类比

## 示例转换

### 原始技术内容：
```
# API 使用说明

POST /api/v1/users
{
  "name": "John",
  "email": "john@example.com"
}

响应: 201 Created
```

### 播客对话内容：
```
男主持: 大家好，欢迎收听本期节目。今天我们来聊聊API开发中一个非常基础但特别重要的功能——用户创建接口。
女主持: 没错！这个功能几乎所有应用都会用到。简单来说，就是当你的应用需要注册新用户的时候，怎么把用户信息告诉服务器。
男主持: 对，流程其实很直观。你把用户的名字和邮箱发给服务器，服务器确认没问题后，就会告诉你——创建成功！
女主持: 听起来很简单，但背后的设计其实挺有讲究的。比如为什么用POST方法而不是GET？这就是一个很值得聊的话题……
```

## 生成命令

```bash
python3 scripts/generate.py \
  --content-file ./tech-article.md \
  --output-file ./generated-podcasts/tech-explainer.mp3 \
  --script-file ./generated-podcasts/tech-explainer-script.json \
  --transcript-file ./generated-podcasts/tech-explainer-transcript.md \
  --locale zh \
  --style tech
```

## 技术播客技巧

- 每期聚焦一个核心概念
- 用类比解释抽象概念
- 包含"这为什么重要"的实用背景
- 避免不加解释的专业术语
- 让对话对初学者友好
