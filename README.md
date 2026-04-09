# 校园异能扭蛋（Playable CLI + Web Playtest）

这是一个可运行的文字抽卡/养成/RPG 原型，支持：

- CLI 测试模式（终端）
- Web Playtest 模式（浏览器）

## 运行方式

### 1) CLI（原模式）

```bash
python3 main.py
```

### 2) Web（浏览器测试）

```bash
python3 web_playtest.py
```

启动后打开：

- `http://127.0.0.1:8000`

页面可直接点击按钮进行：单抽、推图、深渊试炼、秘境远征、每日任务、保存。

## 当前玩法亮点

- **芯片工坊系统**
- **队伍协同系统**
- **深渊试炼模式**
- **校园秘境远征**（5节点随机路线 + 临时增益Buff）
- **失败反馈增强**
- **新手保护机制**（首章前期失败后的一次性战术支援）

## 终端画面优化

- ANSI 颜色高亮（稀有度/敌人品阶/胜率）
- 统一菜单块（减少信息噪音）
- 卡片式战斗信息面板（敌人信息和试炼结算）
- 任务与账号经验进度条

## 遥测日志

- `telemetry_log.jsonl`
- 记录推图胜负、试炼进出与结算、远征节点与结算、存档加载/保存等

## 代码结构

- `main.py`：CLI 入口
- `web_playtest.py`：Web 测试入口（WSGI）
- `campus_game/engine.py`：游戏核心系统（玩法逻辑）
- `campus_game/ui.py`：终端视觉渲染层
- `campus_game/content_database.py`：大规模内容库（角色/敌人/事件/章节/技能）
- `PRODUCT_ROADMAP.md`：后续版本路线图
