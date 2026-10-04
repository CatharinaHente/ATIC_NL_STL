from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Iterable

from lark import Lark, Transformer, UnexpectedInput


GRAMMAR = r"""
?start: expr
?expr: implication
?implication: disjunction ("->" implication)?             -> implication
?disjunction: conjunction ("|" conjunction)*              -> disjunction
?conjunction: temporal_binary ("&" temporal_binary)*       -> conjunction
?temporal_binary: unary (TBIN interval? unary)*            -> temporal_binary

?unary: "!" unary                                          -> negation
      | TEMP interval? "(" expr ")"                        -> temporal_prefix
      | comparison
      | "(" expr ")"

?comparison: arithmetic COMP arithmetic                    -> comparison
           | arithmetic

?arithmetic: sum
?sum: product (ADDOP product)*                             -> sum_expr
?product: factor (MULOP factor)*                           -> product_expr
?factor: SIGNED_NUMBER                                     -> number
       | NAME "(" [arg_list] ")"                           -> function
       | NAME                                              -> name
       | "(" arithmetic ")"

arg_list: expr ("," expr)*                                 -> arg_list
interval: "[" bound "," bound "]"                          -> interval
?bound: SIGNED_NUMBER                                     -> number
      | NAME                                              -> name

TEMP.3: /[GFHO](?=\s*(?:\[|\())/
TBIN.3: /[US](?=\s*(?:\[|\())/
COMP: "<=" | ">=" | "!=" | "=" | "<" | ">"
ADDOP: "+" | "-"
MULOP: "*" | "/"
NAME: /[A-Za-z_][A-Za-z0-9_.]*/
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
"""

PARSER = Lark(GRAMMAR, parser="lalr", maybe_placeholders=False)


@dataclass(frozen=True)
class Node:
    kind: str
    value: str = ""
    children: tuple["Node", ...] = ()


class ToNode(Transformer):
    def name(self, items):
        return Node("name", str(items[0]))

    def number(self, items):
        value = str(items[0])
        try:
            num = float(value)
            value = str(int(num)) if num.is_integer() else format(num, ".12g")
        except ValueError:
            pass
        return Node("number", value)

    def arg_list(self, items):
        return list(items)

    def function(self, items):
        name = str(items[0])
        args = []
        if len(items) > 1:
            args = items[1] if isinstance(items[1], list) else list(items[1:])
        return Node("function", name, tuple(args))

    def interval(self, items):
        return Node("interval", "", tuple(items))

    def comparison(self, items):
        return Node("compare", str(items[1]), (items[0], items[2]))

    def sum_expr(self, items):
        node = items[0]
        i = 1
        while i < len(items):
            node = Node("arith", str(items[i]), (node, items[i + 1]))
            i += 2
        return node

    def product_expr(self, items):
        node = items[0]
        i = 1
        while i < len(items):
            node = Node("arith", str(items[i]), (node, items[i + 1]))
            i += 2
        return node

    def negation(self, items):
        return Node("not", "!", (items[0],))

    def temporal_prefix(self, items):
        op = str(items[0])
        if len(items) == 3:
            return Node("temporal", op, (items[1], items[2]))
        return Node("temporal", op, (items[1],))

    def temporal_binary(self, items):
        node = items[0]
        i = 1
        while i < len(items):
            op = str(items[i])
            if i + 2 < len(items) and isinstance(items[i + 1], Node) and items[i + 1].kind == "interval":
                node = Node("temporal_binary", op, (node, items[i + 1], items[i + 2]))
                i += 3
            else:
                node = Node("temporal_binary", op, (node, items[i + 1]))
                i += 2
        return node

    @staticmethod
    def _commutative(kind, items):
        flat = []
        for item in items:
            if item.kind == kind:
                flat.extend(item.children)
            else:
                flat.append(item)
        if len(flat) == 1:
            return flat[0]
        return Node(kind, "", tuple(sorted(flat, key=canonical)))

    def conjunction(self, items):
        return self._commutative("and", items)

    def disjunction(self, items):
        return self._commutative("or", items)

    def implication(self, items):
        if len(items) == 1:
            return items[0]
        return Node("implies", "->", (items[0], items[1]))


TRANSFORMER = ToNode()


def clean_formula(text: str) -> str:
    text = (text or "").strip()
    replacements = {
        "≤": "<=", "≥": ">=", "≠": "!=", "∧": "&", "∨": "|",
        "¬": "!", "⇒": "->", "→": "->", "□": "G", "◇": "F",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\balways\b", "G", text, flags=re.I)
    text = re.sub(r"\beventually\b", "F", text, flags=re.I)
    text = text.replace(":", ",")
    # Normalize parameterized names such as AND_{i<j} into parser-safe identifiers.
    def _safe_subscript(match):
        base, sub = match.group(1), match.group(2)
        sub = sub.replace("<", "_lt_").replace(">", "_gt_").replace("=", "_eq_")
        sub = re.sub(r"[^A-Za-z0-9_]+", "_", sub).strip("_")
        return f"{base}_{sub}"
    text = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)_\{([^}]+)\}", _safe_subscript, text)
    return text


def parse_formula(text: str) -> tuple[Node | None, str | None]:
    cleaned = clean_formula(text)
    if not cleaned:
        return None, "empty formula"
    try:
        tree = PARSER.parse(cleaned)
        return TRANSFORMER.transform(tree), None
    except (UnexpectedInput, Exception) as exc:
        return None, str(exc).splitlines()[0][:500]


def canonical(node: Node) -> str:
    if node.kind in {"name", "number"}:
        return node.value
    if node.kind == "interval":
        return "[" + ",".join(canonical(c) for c in node.children) + "]"
    if node.kind == "function":
        return f"{node.value}(" + ",".join(canonical(c) for c in node.children) + ")"
    if node.kind == "compare":
        return f"({canonical(node.children[0])}{node.value}{canonical(node.children[1])})"
    if node.kind == "arith":
        return f"({canonical(node.children[0])}{node.value}{canonical(node.children[1])})"
    if node.kind == "not":
        return f"!{canonical(node.children[0])}"
    if node.kind in {"and", "or"}:
        op = "&" if node.kind == "and" else "|"
        return "(" + op.join(canonical(c) for c in node.children) + ")"
    if node.kind == "implies":
        return f"({canonical(node.children[0])}->{canonical(node.children[1])})"
    if node.kind == "temporal":
        if len(node.children) == 2:
            return f"{node.value}{canonical(node.children[0])}({canonical(node.children[1])})"
        return f"{node.value}({canonical(node.children[0])})"
    if node.kind == "temporal_binary":
        if len(node.children) == 3:
            return f"({canonical(node.children[0])}{node.value}{canonical(node.children[1])}{canonical(node.children[2])})"
        return f"({canonical(node.children[0])}{node.value}{canonical(node.children[1])})"
    return f"{node.kind}:{node.value}(" + ",".join(canonical(c) for c in node.children) + ")"


def walk(node: Node) -> Iterable[Node]:
    yield node
    for child in node.children:
        yield from walk(child)


def multiset_f1(a: Counter, b: Counter) -> tuple[float, float, float]:
    if not a and not b:
        return 1.0, 1.0, 1.0
    matched = sum((a & b).values())
    p = matched / sum(a.values()) if a else 0.0
    r = matched / sum(b.values()) if b else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


TOKEN_RE = re.compile(
    r"->|<=|>=|!=|[()\[\],&|!<>+=*/-]|"
    r"\b(?:G|F|H|O|U|S)\b|"
    r"[A-Za-z_][A-Za-z0-9_.]*|"
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
)


def token_counter(text: str) -> Counter:
    return Counter(TOKEN_RE.findall(clean_formula(text)))


def node_label(node: Node) -> str:
    if node.kind in {"name", "number"}:
        return f"{node.kind}:{node.value}"
    return f"{node.kind}:{node.value}"


def node_counter(node: Node | None) -> Counter:
    if node is None:
        return Counter()
    return Counter(node_label(n) for n in walk(node))


def operator_counter(node: Node | None) -> Counter:
    if node is None:
        return Counter()
    operator_kinds = {"compare", "arith", "not", "and", "or", "implies", "temporal", "temporal_binary", "function"}
    return Counter(node_label(n) for n in walk(node) if n.kind in operator_kinds)


def identifier_counter(node: Node | None) -> Counter:
    if node is None:
        return Counter()
    return Counter(n.value for n in walk(node) if n.kind == "name")


def constant_counter(node: Node | None) -> Counter:
    if node is None:
        return Counter()
    return Counter(n.value for n in walk(node) if n.kind == "number")


def compare_formulas(predicted: str, gold: str) -> dict:
    pred_node, pred_error = parse_formula(predicted)
    gold_node, gold_error = parse_formula(gold)

    token_p, token_r, token_f1 = multiset_f1(token_counter(predicted), token_counter(gold))
    ast_p, ast_r, ast_f1 = multiset_f1(node_counter(pred_node), node_counter(gold_node))
    op_p, op_r, op_f1 = multiset_f1(operator_counter(pred_node), operator_counter(gold_node))
    id_p, id_r, id_f1 = multiset_f1(identifier_counter(pred_node), identifier_counter(gold_node))
    num_p, num_r, num_f1 = multiset_f1(constant_counter(pred_node), constant_counter(gold_node))

    pred_canon = canonical(pred_node) if pred_node else ""
    gold_canon = canonical(gold_node) if gold_node else ""
    extras_ids = sorted((identifier_counter(pred_node) - identifier_counter(gold_node)).elements())
    extras_nums = sorted((constant_counter(pred_node) - constant_counter(gold_node)).elements())

    return {
        "pred_parse_ok": pred_node is not None,
        "gold_parse_ok": gold_node is not None,
        "pred_parse_error": pred_error or "",
        "gold_parse_error": gold_error or "",
        "pred_canonical": pred_canon,
        "gold_canonical": gold_canon,
        "canonical_exact_match": bool(pred_node and gold_node and pred_canon == gold_canon),
        "token_precision": token_p,
        "token_recall": token_r,
        "token_f1": token_f1,
        "ast_precision": ast_p,
        "ast_recall": ast_r,
        "ast_f1": ast_f1,
        "operator_precision": op_p,
        "operator_recall": op_r,
        "operator_f1": op_f1,
        "identifier_precision": id_p,
        "identifier_recall": id_r,
        "identifier_f1": id_f1,
        "constant_precision": num_p,
        "constant_recall": num_r,
        "constant_f1": num_f1,
        "extra_identifiers_vs_gold": extras_ids,
        "extra_constants_vs_gold": extras_nums,
    }


SLOT_PATTERNS = {
    "time_bound": re.compile(r"\b(when|how long|deadline|delay|within|time|seconds?|minutes?|duration|soon|while)\b", re.I),
    "threshold": re.compile(r"\b(value|threshold|how (?:high|low|close|far|much)|minimum|maximum|below|above|limit|level)\b", re.I),
    "trigger": re.compile(r"\b(condition|trigger|when|under what|which signal|defines?|necessary|needed|unsafe)\b", re.I),
    "referent": re.compile(r"\b(which|what does|refer|it|they|them|that object|which robot|which valve|which vehicle)\b", re.I),
    "scope": re.compile(r"\b(scope|apply|start|begin|entire|each time|only|both|either|or|and|until|interval)\b", re.I),
    "unit": re.compile(r"\b(unit|units|km/h|mph|m/s|psi|bar|degrees?|metres?|meters?)\b", re.I),
    "external_context": re.compile(r"\b(figure|diagram|profile|provide|external|reference|context|available)\b", re.I),
    "consistency": re.compile(r"\b(conflict|contradict|inconsistent|remove|correction|feasible)\b", re.I),
    "extension": re.compile(r"\b(probability|probabilistic|count|counting|optimization|objective|extension)\b", re.I),
}


def question_slots(question: str) -> set[str]:
    question = question or ""
    return {name for name, pattern in SLOT_PATTERNS.items() if pattern.search(question)}


def slot_scores(predicted_question: str, reference_question: str, defect_type: str) -> dict:
    pred = question_slots(predicted_question)
    gold = question_slots(reference_question)

    defect = (defect_type or "").lower()
    if "temporal" in defect:
        gold.add("time_bound")
    if "numerical" in defect:
        gold.add("threshold")
    if "conditional" in defect:
        gold.add("trigger")
    if "referential" in defect:
        gold.add("referent")
    if "semantic" in defect or "scope" in defect:
        gold.add("scope")
    if "unit" in defect:
        gold.add("unit")
    if "external" in defect:
        gold.add("external_context")
    if "inconsistent" in defect or "infeasible" in defect:
        gold.add("consistency")
    if any(x in defect for x in ("probabilistic", "counting", "objective")):
        gold.add("extension")

    p, r, f1 = multiset_f1(Counter(pred), Counter(gold))
    return {
        "predicted_slots": sorted(pred),
        "gold_slots": sorted(gold),
        "clarification_slot_precision": p,
        "clarification_slot_recall": r,
        "clarification_slot_f1": f1,
    }
