#!/usr/bin/env python3
"""根据 references/coaching-rules.md 的规则判断本轮是否适合给建议。"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict

if __package__:
    from .prompt_rater import rate
else:
    from prompt_rater import rate


def score_prompt(prompt: str) -> int:
    return rate(prompt).score


DEEP_WORK_MARKERS = (
    r"\bstack\s*trace\b",
    r"\btraceback\b",
    r"\bsegfault\b",
    r"```",
    r"\bworking on\b",
    r"\bin the middle of\b",
    r"\bfeeling\b",
    r"\bvent(ing)?\b",
    r"\bjust\s+(do|write|give)\b.*\bno\s+(commentary|extras|tips)\b",
    r"异常堆栈|堆栈跟踪|段错误|正在排查|只是想倾诉|只给(?:结果|答案|代码)|直接给(?:结果|答案|代码)",
)
SUPPRESS_MARKERS = (
    r"\bstop\s+(with\s+)?the\s+tips\b",
    r"\bno\s+coaching\b",
    r"\bquiet mode\b",
    r"\bdon[’']?t coach\b",
    r"(?:停止|暂停|关闭)(?:指令)?(?:指导|点拨|点评)|(?:别|不要)(?:再)?(?:指导|点评|点拨)我",
)

# 一轮只取第一条符合条件的建议。
TIP_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\bhelp me with my email\b|\bwrite (a |an )?email\b|(?:帮我)?(?:写|起草)(?:一)?封邮件", re.IGNORECASE),
     "先给收件人和你希望对方采取的行动，可以减少来回修改。",
     "例如「给直属经理写封邮件，说明周五不能参会，并建议改为异步同步进度。」"),
    (re.compile(r"^(?:thoughts|你?怎么(?:看|想)|有(?:什么|啥)建议)[?？。]?$|\bany thoughts\b", re.IGNORECASE),
     "请对方聚焦一个你关心的方面，例如论据、结构或遗漏。",
     "例如「哪条论点最薄弱，需要补什么证据？」"),
    (re.compile(r"\b(?:current|latest|today|news|price|version)\b|最新|今天|当前(?:价格|版本)|现价", re.IGNORECASE),
     "涉及最新信息时，可以指定核对的来源和时间。",
     "例如「查官方价格页，给出当前价格、核对日期和链接。」"),
    (re.compile(r"\b(can|could) you (make|give|do|write)\b.*\b(better|nicer|cleaner)\b|改好一点|优化一下|写得更好", re.IGNORECASE),
     "把「更好」改成一项可以检查的目标。",
     "例如「删掉三成篇幅，保留所有数据和结论。」"),
    (re.compile(r"\b(list|table|json|markdown)\b|表格|列表|分点", re.IGNORECASE),
     "",
     ""),
]


@dataclass
class Decision:
    prompt: str
    coach: bool
    reason: str
    tip: str = ""
    tip_example: str = ""
    gates: dict[str, str] = field(default_factory=dict)


def is_deep_work(prompt: str) -> bool:
    return any(re.search(p, prompt, re.IGNORECASE) for p in DEEP_WORK_MARKERS) or len(prompt) > 800


def is_suppression(prompt: str) -> bool:
    return any(re.search(p, prompt, re.IGNORECASE) for p in SUPPRESS_MARKERS)


def pick_tip(prompt: str) -> tuple[str, str]:
    for pattern, tip, example in TIP_RULES:
        if pattern.search(prompt):
            return tip, example
    return "", ""


def classify(prompt: str, previous_tip_given: bool = False) -> Decision:
    decision = Decision(prompt=prompt, coach=False, reason="")
    decision.gates["1_previous_tip"] = "blocked" if previous_tip_given else "pass"
    decision.gates["suppression"] = "blocked" if is_suppression(prompt) else "pass"

    if previous_tip_given:
        decision.reason = "上一轮已经给过建议。"
        return decision
    if is_suppression(prompt):
        decision.reason = "用户已表示暂时不需要指导。"
        return decision

    prompt_score = score_prompt(prompt)
    decision.gates["2_prompt_score"] = f"{prompt_score}/10"
    if prompt_score >= 8:
        decision.reason = "指令已经足够具体。"
        return decision

    decision.gates["3_deep_work"] = "blocked" if is_deep_work(prompt) else "pass"
    if is_deep_work(prompt):
        decision.reason = "用户正在集中处理任务，本轮直接交付。"
        return decision

    tip, example = pick_tip(prompt)
    decision.gates["4_specificity"] = "skip" if not tip else "pass"
    if not tip:
        decision.reason = "本轮没有适用的具体建议。"
        return decision

    decision.coach = True
    decision.reason = "本轮适合给一条建议。"
    decision.tip = tip
    decision.tip_example = example
    decision.gates["5_single_high_impact"] = "pass"
    return decision


def render_human(d: Decision) -> str:
    head = "给建议" if d.coach else "直接交付"
    out = [f"[{head}] {d.reason}"]
    if d.coach:
        out.append(f"⚡ 指令建议　{d.tip}")
        if d.tip_example:
            out.append(d.tip_example)
    out.append(f"判断记录　{d.gates}")
    return "\n".join(out)


def sample_run(as_json: bool = False) -> int:
    cases = [
        ("帮我写封邮件", False),
        ("给远程办公的用户写一段 200 字以内的降噪耳机介绍，用 Markdown 列表呈现，避免营销套话。", False),
        ("你怎么看？", False),
        ("帮我优化一下", True),
        ("停止指令指导，帮我写封邮件", False),
    ]
    decisions = [classify(prompt, previous_tip_given=prev) for prompt, prev in cases]
    if as_json:
        print(json.dumps([asdict(d) for d in decisions], ensure_ascii=False, indent=2))
        return 0
    for d in decisions:
        print(render_human(d))
        print("-" * 60)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="判断本轮是否适合给一条指令建议。")
    parser.add_argument("--prompt", type=str, help="本轮的用户指令")
    parser.add_argument("--previous-tip-given", action="store_true", help="上一轮已经给过建议")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--sample", action="store_true", help="运行内置示例")
    args = parser.parse_args(argv)

    if args.sample:
        return sample_run(args.json)

    if not args.prompt:
        parser.error("使用 --sample 运行内置示例，或用 --prompt 提供指令。")

    d = classify(args.prompt, previous_tip_given=args.previous_tip_given)
    if args.json:
        print(json.dumps(asdict(d), ensure_ascii=False, indent=2))
    else:
        print(render_human(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
