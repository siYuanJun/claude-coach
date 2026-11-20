# claude-coach

This standalone Agent Skill offers brief coaching tips after normal responses when it spots a way to improve the user's next prompt.

The skill files come from Alireza Rezvani's [claude-skills repository](https://github.com/alirezarezvani/claude-skills/tree/f8593c4941210a621a6629ce1da9e07897976d5f/engineering/claude-coach/skills/claude-coach). They are distributed under the [MIT License](LICENSE).

## Use in Codex

```sh
npx skills add https://github.com/siYuanJun/claude-coach --skill claude-coach --agent codex --global
```

In a new Codex turn, ask `Use $claude-coach. I mainly use AI for coding and research.` Once activated in the conversation, the skill looks for opportunities to add one useful tip after a response.

The helper scripts require Python 3.11 or newer. Use `python3.11` if your default `python3` is older.

## Contents

- `SKILL.md` — main skill instructions
- `references/cheat-codes.md` — ranked glossary of Claude power-user techniques
- `references/coaching-rules.md` — 5-gate decision tree for when to coach
- `scripts/cheat_code_filter.py` — filter the glossary by use case
- `scripts/prompt_rater.py` — score a prompt 0-10
- `scripts/coach_tip_classifier.py` — run the 5-gate decision tree on a turn

For the full Claude Code plugin, see the [upstream plugin README](https://github.com/alirezarezvani/claude-skills/blob/f8593c4941210a621a6629ce1da9e07897976d5f/engineering/claude-coach/README.md).
