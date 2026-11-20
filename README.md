# claude-coach 中文版

这是一个在任务交付后给出简短指令建议的 Skill。首次启用时，它按你的用途推荐技巧。日常协作中，遇到能减少澄清或返工的机会，会在回复末尾给一条建议。也可以随时请它点评一条指令。

本项目是 Alireza Rezvani 的 `claude-coach` 技能的中文版本，基于[上游提交](https://github.com/alirezarezvani/claude-skills/tree/f8593c4941210a621a6629ce1da9e07897976d5f/engineering/claude-coach/skills/claude-coach)，采用 [MIT 许可证](LICENSE)。

## 在 Codex 中使用

```sh
npx skills add https://github.com/siYuanJun/claude-coach --skill claude-coach --agent codex --global
```

安装后在新回合中说「用 `$claude-coach`，我主要用 AI 写代码和排查问题。」主动点评可以说「点评我刚才那条指令」。需要暂停时说「停止指令指导」。

## 随附工具

脚本需要 Python 3.11 或更高版本。本机的 `python3` 版本较旧时可使用 `python3.11`。CLI 参数和 JSON 字段沿用上游格式。

```sh
python3.11 scripts/cheat_code_filter.py --use-cases "编程，调研"
python3.11 scripts/prompt_rater.py --prompt "帮我写封邮件"
python3.11 scripts/coach_tip_classifier.py --prompt "你怎么看？"
```

- [技能入口](SKILL.md) 包含开启方式、反馈格式和中文示例。
- [使用技巧](references/cheat-codes.md) 按使用场景和难度组织。
- [反馈规则](references/coaching-rules.md) 说明什么时候提示，什么时候直接交付。
- [上游插件说明](https://github.com/alirezarezvani/claude-skills/blob/f8593c4941210a621a6629ce1da9e07897976d5f/engineering/claude-coach/README.md) 提供完整 Claude Code 插件的用法。
