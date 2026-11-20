#!/usr/bin/env python3
"""按清晰度、约束、格式和受众对指令评分，并给出改写建议。"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict

CLARITY_VERBS = ("write", "draft", "summarize", "review", "compare", "explain", "translate", "rewrite", "list", "rank", "score", "outline", "design", "debug", "refactor", "test")
CHINESE_VERBS = re.compile(r"起草|改写|撰写|写|总结|审阅|评审|比较|解释|翻译|列出|排序|评分|设计|排查|重构|测试|生成|整理|检查|修复")
HAN_CHARACTERS = re.compile(r"[\u3400-\u9fff]")
LENGTH_TOKENS = (
    r"\b\d+\s*(words?|sentences?|paragraphs?|bullets?|lines?|pages?|tokens?)\b",
    r"one\s+(sentence|paragraph|line)", r"short", r"brief", r"detailed",
    r"(?:\d+|[一二两三四五六七八九十百千]+)\s*(?:个?字|句|段|条|行|页|[%％])",
)
CONSTRAINT_TOKENS = (
    r"\bno\s+(more|less)\s+than\b", r"\bmust\b", r"\bcannot\b", r"\bavoid\b", r"\bonly\b",
    r"不超过|至少|最多|以内|必须|不得|避免|仅限|只改|只保留|控制在|截止",
)
FORMAT_TOKENS = (
    r"(?<![A-Za-z0-9_])(?:markdown|json|yaml|csv)(?![A-Za-z0-9_])",
    r"\b(?:table|bullet|list|code|email|memo|outline)\b",
    r"表格|列表|分点|大纲|备忘录|代码块|电子邮件|写(?:一)?封邮件",
)
AUDIENCE_TOKENS = (
    r"\bfor\s+(my|a|the)\s+[A-Za-z][A-Za-z\- ]+\b", r"\btargeting\s+\w+",
    r"\b(?:non-technical|technical|executive\w*|junior|senior|team|customer\w*|remote workers)\b",
    r"(?:写给|给|面向|供|适合|读者是|受众是)[^，。？！：\n]{0,18}"
    r"(?:同事|经理|客户|工程师|负责人|初学者|读者|团队|用户|学生|家长|管理层|开发者)",
)
ROLE_TOKENS = (r"you are\b", r"act as\b", r"as a\b", r"你是|请以.{1,24}的视角|作为一名")
DIMENSION_LABELS = {
    "clarity": "清晰度",
    "constraint": "约束",
    "format": "格式",
    "audience": "受众",
    "length_bonus": "细节加分",
}


@dataclass
class Rating:
    prompt: str
    clarity: int = 0
    constraint: int = 0
    fmt: int = 0
    audience: int = 0
    score: int = 0
    what_worked: str = ""
    what_to_improve: str = ""
    better_version: str = ""
    breakdown: dict[str, str] = field(default_factory=dict)


def _has_any(text: str, patterns) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _verb_strength(text: str) -> int:
    hits = sum(1 for v in CLARITY_VERBS if re.search(rf"\b{v}\b", text, re.IGNORECASE))
    hits += len(set(CHINESE_VERBS.findall(text)))
    return min(hits, 2)


def rate(prompt: str) -> Rating:
    p = prompt.strip()
    rating = Rating(prompt=p)

    verb_score = _verb_strength(p)
    length_ok = _has_any(p, LENGTH_TOKENS)
    han_count = len(HAN_CHARACTERS.findall(p))
    # 中文通常不以空格分词，按每两个汉字估算一个词的长度。
    word_count = len(HAN_CHARACTERS.sub("", p).split()) + han_count // 2
    is_vague_open = p.endswith(("?", "？")) and word_count < 8
    length_bonus = int(word_count >= 12)

    rating.clarity = min(3, verb_score + int(not is_vague_open) + int(word_count >= 6))
    rating.constraint = 2 if length_ok or _has_any(p, CONSTRAINT_TOKENS) else 0
    rating.fmt = 2 if _has_any(p, FORMAT_TOKENS) else 0
    rating.audience = 2 if (_has_any(p, AUDIENCE_TOKENS) or _has_any(p, ROLE_TOKENS)) else 0

    raw = rating.clarity + rating.constraint + rating.fmt + rating.audience
    rating.score = min(10, raw + length_bonus)

    rating.breakdown = {
        "clarity": f"{rating.clarity}/3",
        "constraint": f"{rating.constraint}/2",
        "format": f"{rating.fmt}/2",
        "audience": f"{rating.audience}/2",
        "length_bonus": f"+{length_bonus}",
    }

    if rating.score >= 8:
        rating.what_worked = "指令包含多项具体要求，可以直接开始。"
        rating.what_to_improve = "有需要时，可以让 AI 在初稿之后按你的标准自查一轮。"
        rating.better_version = p
    elif rating.score >= 5:
        worked = []
        if rating.clarity >= 2:
            worked.append("任务动作明确")
        if rating.constraint:
            worked.append("有具体约束")
        if rating.fmt:
            worked.append("指定了输出格式")
        if rating.audience:
            worked.append("给出了受众或角色")
        rating.what_worked = "、".join(worked) or "已有足够信息开始尝试"
        if not rating.audience:
            rating.what_to_improve = "说清交付给谁，或者希望 AI 采用什么视角。"
        elif not rating.constraint:
            rating.what_to_improve = "补一项可检查的要求，比如字数上限、必须包含或需要避免的内容。"
        elif not rating.fmt:
            rating.what_to_improve = "说清要的是 Markdown 表格、JSON、列表还是正文。"
        else:
            rating.what_to_improve = "补一项容易引起返工的约束。"
        rating.better_version = _augment(p, rating)
    else:
        rating.what_worked = "已给出一个可继续细化的主题。"
        rating.what_to_improve = "把问题落到一个具体动作，并补充对结果有影响的长度、受众和格式。"
        rating.better_version = _augment(p, rating, aggressive=True)

    return rating


def _augment(prompt: str, rating: Rating, aggressive: bool = False) -> str:
    chinese = bool(HAN_CHARACTERS.search(prompt))
    additions: list[str] = []
    if not rating.constraint:
        additions.append("控制在 200 字以内" if chinese else "in 200 words")
    if not rating.audience:
        additions.append("写给非技术读者" if chinese else "for a non-technical reader")
    if not rating.fmt:
        additions.append("用 Markdown 分点呈现" if chinese else "as markdown bullets")
    if not additions:
        return prompt
    if chinese:
        base = prompt.rstrip(" .?。？！!").removesuffix("吗")
        if aggressive and not _verb_strength(prompt):
            base = f"请围绕「{base}」给出有重点的回答"
        return f"{base}。{'，'.join(additions)}。"
    base = prompt.rstrip(" .?")
    suffix = ", ".join(additions)
    if aggressive and not any(v in prompt.lower() for v in CLARITY_VERBS):
        base = f"Write a focused response to: {base}"
    return f"{base}, {suffix}."


def render_human(r: Rating) -> str:
    breakdown = "，".join(f"{DIMENSION_LABELS[key]} {value}" for key, value in r.breakdown.items())
    return (
        f"**原指令**　{r.prompt}\n"
        f"**评分**　{r.score}/10（{breakdown}）\n"
        f"**做得好的地方**　{r.what_worked}\n"
        f"**最值得改的地方**　{r.what_to_improve}\n"
        f"**下次可以这样说**　{r.better_version}"
    )


def sample_run(as_json: bool = False) -> int:
    samples = [
        "帮我写封邮件",
        "给远程办公的用户写一段 200 字以内的降噪耳机介绍，用 Markdown 列表呈现，避免营销套话。",
        "你怎么看？",
    ]
    ratings = [rate(s) for s in samples]
    if as_json:
        print(json.dumps([asdict(r) for r in ratings], ensure_ascii=False, indent=2))
        return 0
    for r in ratings:
        print(render_human(r))
        print("-" * 60)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按四个维度为一条指令评分，满分 10 分。")
    parser.add_argument("--prompt", type=str, help="要点评的指令")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--sample", action="store_true", help="运行内置示例")
    args = parser.parse_args(argv)

    if args.sample:
        return sample_run(args.json)

    if not args.prompt:
        parser.error("使用 --sample 运行内置示例，或用 --prompt 提供指令。")

    r = rate(args.prompt)
    if args.json:
        print(json.dumps(asdict(r), ensure_ascii=False, indent=2))
    else:
        print(render_human(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
