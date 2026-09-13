from app.llm.base import parse_model, repair_json
from app.schemas import LLMCards


def test_repair_latex_backslashes_and_trailing_commas():
    raw = '{"cards": [{"front": "留数定理公式 $\\oint f(z)dz$ 与 \\frac{1}{2}", "back": "第一行\n第二行", "source_index": 1,},]}'
    fixed = repair_json(raw)
    cards = parse_model(LLMCards, fixed)
    assert cards.cards[0].front == "留数定理公式 $\\oint f(z)dz$ 与 \\frac{1}{2}"
    assert cards.cards[0].back == "第一行\n第二行"


def test_parse_model_repairs_automatically():
    raw = '```json\n{"cards": [{"front": "$\\alpha$", "back": "ok", "source_index": 0}]}\n```'
    assert parse_model(LLMCards, raw).cards[0].front == "$\\alpha$"


def test_latex_escape_collisions_survive_strict_parse():
    raw = '{"cards": [{"front": "$\\frac{1}{2} + \\theta \\to \\nabla$ 和换行\\n第二行", "back": "\\beta", "source_index": 0}]}'
    card = parse_model(LLMCards, raw).cards[0]
    assert card.front == "$\\frac{1}{2} + \\theta \\to \\nabla$ 和换行\n第二行"
    assert card.back == "\\beta"
