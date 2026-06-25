# VocabBuilder · 单词学习助手

一个帮助记录生词、并通过每日填空复习来巩固记忆的本地 Web 应用。
遇到不认识的英文单词、短语动词、习语或表达，随手存下来，应用会用 AI 自动补全释义，并在每天的复习里把它们随机出成填空题。

## 功能

- 📝 **快速记录**：支持单词、短语动词（phrasal verb）、习语（idiom）、表达（expression）
- 🤖 **AI 自动释义**：自动生成中文释义、英文定义，以及例句的中文翻译
- 🔊 **音标**：优先取自 Wiktionary，缺失时由 AI 补全（英式 RP + 美式 GenAm）
- 🎯 **每日复习**：以填空题形式复习，**单词与例句随机打乱顺序**，加大难度
- ⚖️ **加权抽取**：越熟悉的词出现得越少，把复习时间留给薄弱的词
- 📥 **批量录入**：用 `单词 | 例句` 的格式，一行一个批量添加

## 技术栈

- Python + [Flask](https://flask.palletsprojects.com/)
- SQLite（本地数据库）
- [Anthropic Claude API](https://docs.anthropic.com/)（释义与例句生成）

## 安装

```bash
# 1. 克隆仓库
git clone https://github.com/kulindexiuxing/vocab_app.git
cd vocab_app

# 2. 安装依赖
pip install -r requirements.txt
```

## 配置

应用通过环境变量读取 Anthropic API 密钥（**密钥不写进代码**）：

```bash
export ANTHROPIC_API_KEY="你的-anthropic-api-key"
```

> 在 Anthropic 控制台申请密钥：https://console.anthropic.com/

## 运行

```bash
python3 app.py
```

启动后会自动打开浏览器，也可手动访问：

- 添加生词：http://localhost:5001
- 每日复习：http://localhost:5001/review

按 `Ctrl+C` 退出。

## 项目结构

```
app.py          Flask 路由与启动入口
db.py           SQLite 读写（含复习单词的随机抽取）
ai.py           Claude API 调用（释义、例句、音标生成）
phonetics.py    Wiktionary 音标抓取
templates/      页面模板（添加页、复习页）
.githooks/      提交前钩子：拦截密钥与个人信息
```

## 说明

- `vocab.db`（你的个人单词数据）已被 `.gitignore` 排除，不会进入仓库。
- 仓库内置 `.githooks/pre-commit` 钩子，提交前自动拦截密钥与个人信息。克隆后启用一次即可：
  ```bash
  git config core.hooksPath .githooks
  ```
