# 智能日报生成器

从 GitHub / 飞书自动采集工作数据，生成结构化日报并推送。

## 快速开始

```bash
# 安装依赖
uv sync

# 复制并填写配置
cp config.yaml.example config.yaml
```

## 项目结构

```
collector/   # 采集层
generator/   # 生成层
notifier/    # 推送层
shared/      # 共享基础层
tests/       # 测试
```
