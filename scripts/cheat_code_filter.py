#!/usr/bin/env python3
"""按使用场景筛选并排序 references/cheat-codes.md 中的技巧。"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

USE_CASE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "writing": ("write", "draft", "tone", "audience", "rewrite", "edit", "voice", "format",
                "写作", "起草", "文案", "语气", "受众", "邮件", "风格"),
    "coding": ("code", "function", "bug", "debug", "review", "test", "refactor", "stack",
               "代码", "接口", "排查", "报错", "评审", "测试", "调试"),
    "research": ("research", "search", "source", "cite", "summary", "synthes", "compare",
                 "调研", "查找", "来源", "出处", "总结", "论据"),
    "learning": ("explain", "teach", "concept", "understand", "tutorial", "learn",
                 "解释", "概念", "理解", "教程", "学习", "示例"),
    "business": ("plan", "strategy", "memo", "decision", "tradeoff", "stakeholder", "report",
                 "规划", "方案", "决策", "取舍", "项目", "报告"),
    "data": ("json", "table", "structured", "parse", "format", "schema", "extract",
             "数据", "表格", "结构", "字段", "提取", "查询"),
}
USE_CASE_ALIASES = {
    "写作": "writing", "编程": "coding", "写代码": "coding", "排查问题": "coding",
    "调研": "research", "研究": "research", "学习": "learning",
    "业务": "business", "业务工作": "business", "数据": "data", "数据分析": "data",
}
LEVEL_LABELS = {"Beginner": "入门", "Intermediate": "进阶", "Advanced": "高级"}
LEVEL_NAMES = {label: name for name, label in LEVEL_LABELS.items()}

DEFAULT_GLOSSARY = Path(__file__).resolve().parent.parent / "references" / "cheat-codes.md"

TIER_HEADING = re.compile(r"^##\s+(?:Tier\s+|第\s*)(\d+)", re.IGNORECASE)
TECHNIQUE_HEADING = re.compile(
    r"^###\s+(?P<title>.+?)\s*[（(](?P<level>Beginner|Intermediate|Advanced|入门|进阶|高级)[）)]\s*$",
    re.IGNORECASE,
)
EXAMPLE_LINE = re.compile(r"^\*\*(?:Example:|示例[：:]?)\*\*\s+(?P<text>.+)$")


@dataclass
class Technique:
    title: str
    level: str
    tier: int
    explanation: str
    example: str
    score: float = 0.0


def parse_glossary(path: Path) -> list[Technique]:
    if not path.exists():
        raise FileNotFoundError(f"找不到使用技巧文件 {path}")
    techniques: list[Technique] = []
    current_tier = 99
    current: Technique | None = None
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        tier_match = TIER_HEADING.match(line)
        if tier_match:
            current_tier = int(tier_match.group(1))
            continue
        tech_match = TECHNIQUE_HEADING.match(line)
        if tech_match:
            if current is not None:
                techniques.append(current)
            level = tech_match.group("level")
            current = Technique(
                title=tech_match.group("title").strip(),
                level=LEVEL_NAMES.get(level, level.capitalize()),
                tier=current_tier,
                explanation="",
                example="",
            )
            continue
        if current is None:
            continue
        ex_match = EXAMPLE_LINE.match(line)
        if ex_match:
            current.example = ex_match.group("text").strip()
            continue
        if line.strip() and not line.startswith("---") and not line.startswith("##"):
            if not current.explanation:
                current.explanation = line.strip()
    if current is not None:
        techniques.append(current)
    return techniques


def score_technique(tech: Technique, use_cases: Iterable[str]) -> float:
    text = f"{tech.title} {tech.explanation} {tech.example}".lower()
    score = 0.0
    matched_use_cases = 0
    for uc in use_cases:
        uc = uc.strip().lower()
        keywords = USE_CASE_KEYWORDS.get(USE_CASE_ALIASES.get(uc, uc), (uc,))
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            matched_use_cases += 1
            score += hits
    tier_weight = max(0.0, 6 - tech.tier) * 1.5
    level_weight = {"Beginner": 2.0, "Intermediate": 1.0, "Advanced": 0.5}.get(tech.level, 1.0)
    return score + tier_weight + level_weight + matched_use_cases * 0.5


def rank(techniques: list[Technique], use_cases: list[str], top: int) -> list[Technique]:
    for tech in techniques:
        tech.score = score_technique(tech, use_cases)
    techniques.sort(key=lambda t: (-t.score, t.tier, t.title))
    return techniques[:top]


def render_human(picks: list[Technique]) -> str:
    if not picks:
        return "没有找到匹配的技巧。"
    out: list[str] = []
    for tech in picks:
        out.append(f"- **{tech.title}**（{LEVEL_LABELS[tech.level]}）{tech.explanation}")
        if tech.example:
            out.append(f"  _{tech.example}_")
    return "\n".join(out)


def sample_run(as_json: bool = False) -> int:
    sample_path = DEFAULT_GLOSSARY
    if not sample_path.exists():
        print("找不到参考文件 references/cheat-codes.md。", file=sys.stderr)
        return 1
    use_cases = ["写作", "编程"]
    picks = rank(parse_glossary(sample_path), use_cases, 5)
    if as_json:
        print(json.dumps({"use_cases": use_cases, "picks": [asdict(t) for t in picks]}, ensure_ascii=False, indent=2))
        return 0
    print(render_human(picks))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按使用场景筛选 AI 使用技巧。")
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY, help="使用技巧文件的路径")
    parser.add_argument("--use-cases", type=str, default="", help="以逗号分隔的场景，如写作、编程、调研、学习、业务、数据分析")
    parser.add_argument("--top", type=int, default=7, help="要返回的技巧数量，默认 7 项")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--sample", action="store_true", help="运行内置示例")
    args = parser.parse_args(argv)

    if args.sample:
        return sample_run(args.json)

    if not args.use_cases:
        parser.error("使用 --sample 运行内置示例，或用 --use-cases 指定使用场景。")

    use_cases = [u.strip() for u in re.split(r"[,，、]", args.use_cases) if u.strip()]
    try:
        techniques = parse_glossary(args.glossary)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    picks = rank(techniques, use_cases, args.top)

    if args.json:
        print(json.dumps({"use_cases": use_cases, "picks": [asdict(t) for t in picks]}, ensure_ascii=False, indent=2))
    else:
        print(render_human(picks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
