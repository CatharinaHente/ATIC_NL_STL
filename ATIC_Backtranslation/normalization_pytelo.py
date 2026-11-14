import re

from antlr4 import InputStream, CommonTokenStream, Token
from antlr4.error.ErrorListener import ErrorListener

from stl import STLFormula, STLAbstractSyntaxTreeExtractor
from stl import Operation, RelOperation

from stlLexer import stlLexer
from stlParser import stlParser

import matplotlib.pyplot as plt



#DEFINITIONS
INF = 1_000_000_000

EDGE_TABLE = {}

_UNICODE = {"≥": ">=", "≤": "<=", "→": "=>", "->": "=>", "∧": "&&", "∨": "||", "¬": "!"}


_ALIAS = {'&': '&&', '/\\': '&&', '|': '||', '\\/': '||', '~': '!', '<>': 'F', '[]': 'G'}
ONCE, HIST, SINCE = 10, 11, 12            
_PAST = {'O': ONCE, 'H': HIST, 'S': SINCE}
_PAST_NAMES = {ONCE: "ONCE", HIST: "HISTORICALLY", SINCE: "SINCE"}
TEMPORAL = {Operation.ALWAYS, Operation.EVENT, Operation.UNTIL, ONCE, HIST, SINCE}


###TEXT NORMALISATION

###handle rise and fall
def _extract_edge_ops(s):
    pat = re.compile(r'(?<![A-Za-z0-9_])(rise|fall)\s*\(', re.I)
    out, i = [], 0
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:]); break
        out.append(s[i:m.start()])
        depth, j = 1, m.end()
        while j < len(s) and depth:
            depth += (s[j] == '(') - (s[j] == ')')
            j += 1
        if depth:
            raise SyntaxError(f"unbalanced parentheses after {m.group(1)}(")
        inner = s[m.end(): j - 1].strip()
        kind = m.group(1).lower()
        key = f"{kind.upper()}_EVT_{len(EDGE_TABLE)}"
        EDGE_TABLE[key] = (kind, inner)
        out.append(f"({key} > 0)")
        i = j
    return "".join(out)


###handle math operation discrepancies and unbound time
def normalize(s):
    s = s.strip()
    for k, v in _UNICODE.items():
        s = s.replace(k, v)
    s = _extract_edge_ops(s)
    s = re.sub(r'(?<![<>!=])==(?!=)', '=', s)
    # unbounded unary temporal ops -> [0, INF]  (G, F future; H, O past)
    s = re.sub(r'(?<![A-Za-z0-9_])([GF])(?![A-Za-z0-9_])(?!\s*\[)', rf'\1[0, {INF}]', s)
    s = re.sub(r'(?<![A-Za-z0-9_])([HO])(?=\s*\()', rf'\1[0, {INF}]', s)
    s = re.sub(r'(?<=\))(\s*)([US])(?!\s*\[)(?=\s*\()', rf'\1\2[0, {INF}]', s)
    return s



###MORE TOLERANT AST EXTRACTOR

###keep symbolic right-hand sides like "Passive" or another signal (read comparison expr correctly)
def _num_or_str(text):
    try:
        return float(text)
    except ValueError:
        return text          


###O, H, S tree nodes added
class PSTLFormula(STLFormula):
    def __init__(self, op, **kw):
        super().__init__(op)
        self.low, self.high = kw['low'], kw['high']
        if op == SINCE:
            self.left, self.right = kw['left'], kw['right']
        else:
            self.child = kw['child']

    def __str__(self):
        sym = {ONCE: 'O', HIST: 'H', SINCE: 'S'}[self.op]
        if self.op == SINCE:
            return f"({self.left} {sym}[{self.low}, {self.high}] {self.right})"
        return f"({sym}[{self.low}, {self.high}] {self.child})"


###PYTELO's STLAbstractSyntaxTreeExtractor but with O, S, H
class RobustExtractor(STLAbstractSyntaxTreeExtractor):
    def visitFormula(self, ctx):
        t = ctx.op.text
        op = _PAST.get(t) or Operation.getCode(_ALIAS.get(t, t))
        if op in (Operation.AND, Operation.OR):
            children = []
            for side in (self.visit(ctx.left), self.visit(ctx.right)):
                if side.op == op:
                    children.extend(side.children)
                else:
                    children.append(side)
            return STLFormula(op, children=children)
        if op == Operation.IMPLIES:
            return STLFormula(op, left=self.visit(ctx.left), right=self.visit(ctx.right))
        if op == Operation.NOT:
            return STLFormula(op, child=self.visit(ctx.child))
        if op == Operation.UNTIL:
            return STLFormula(op, left=self.visit(ctx.left), right=self.visit(ctx.right),
                              low=float(ctx.low.text), high=float(ctx.high.text))
        if op in (Operation.ALWAYS, Operation.EVENT):
            return STLFormula(op, child=self.visit(ctx.child),
                              low=float(ctx.low.text), high=float(ctx.high.text))
        if op in (ONCE, HIST):
            return PSTLFormula(op, child=self.visit(ctx.child),
                               low=float(ctx.low.text), high=float(ctx.high.text))
        if op == SINCE:
            return PSTLFormula(op, left=self.visit(ctx.left), right=self.visit(ctx.right),
                               low=float(ctx.low.text), high=float(ctx.high.text))
        raise ValueError(f"unknown operator {ctx.op.text!r}")

    def visitBooleanExpr(self, ctx):
        if ctx.atom is not None:           # bare Boolean signal, e.g. "goal_1"
            return STLFormula(Operation.PRED, relation=RelOperation.EQ,
                              variable=ctx.atom.text, threshold=True)
        if ctx.op.text.lower() in ('true', 'false'):
            return STLFormula(Operation.BOOL, value=ctx.op.text.lower() == 'true')
        return STLFormula(Operation.PRED,
                          relation=RelOperation.getCode(ctx.op.text),
                          variable=ctx.left.getText(),
                          threshold=_num_or_str(ctx.right.getText()))




###STRICT PARSE

###how antlr reports errors
class RaiseOnError(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise SyntaxError(f"col {column}: {msg}")

###MAIN parsing function
def parse_formula(raw: str):
    s = normalize(raw)
    lexer = stlLexer(InputStream(s))
    lexer.removeErrorListeners(); lexer.addErrorListener(RaiseOnError())
    parser = stlParser(CommonTokenStream(lexer))
    parser.removeErrorListeners(); parser.addErrorListener(RaiseOnError())
    tree = parser.stlProperty()
    if parser.getCurrentToken().type != Token.EOF:
        raise SyntaxError(f"unparsed trailing input: {parser.getCurrentToken().text!r}")
    return RobustExtractor().visit(tree), s



###AST HELPERS
def kids(n):
    if n.op in (Operation.AND, Operation.OR):
        return list(n.children)
    if n.op in (Operation.IMPLIES, Operation.UNTIL, SINCE):
        return [n.left, n.right]
    if n.op in (Operation.NOT, Operation.ALWAYS, Operation.EVENT, ONCE, HIST):
        return [n.child]
    return []

def label(n):
    if n.op == Operation.BOOL:
        return str(n.value)
    if n.op == Operation.PRED:
        if n.variable in EDGE_TABLE:
            kind, inner = EDGE_TABLE[n.variable]
            return f"{kind}({inner})"
        if n.threshold is True:                     # bare Boolean signal
            return n.variable
        th = f"{n.threshold:g}" if isinstance(n.threshold, float) else n.threshold
        return f"{n.variable} {RelOperation.getString(n.relation)} {th}"
    name = _PAST_NAMES.get(n.op) or Operation.getName(n.op).upper()
    if n.op in TEMPORAL:
        hi = "∞" if n.high >= INF else f"{n.high:g}"
        return f"{name}\n[{n.low:g}, {hi}]"
    return name




###TEXT TREE
def print_tree(n, prefix="", is_last=True, is_root=True):
    text = label(n).replace("\n", " ")
    if is_root:
        print(text); child_prefix = ""
    else:
        print(prefix + ("└── " if is_last else "├── ") + text)
        child_prefix = prefix + ("    " if is_last else "│   ")
    ch = kids(n)
    for i, c in enumerate(ch):
        print_tree(c, child_prefix, i == len(ch) - 1, is_root=False)



###DRAW TREE
def draw_ast(root, title=None):
    pos, counter = {}, [0]

    def layout(n, depth=0):
        ch = kids(n)
        if not ch:
            x = counter[0]; counter[0] += 1
        else:
            xs = [layout(c, depth + 1) for c in ch]
            x = sum(xs) / len(xs)
        pos[id(n)] = (x, -depth)
        return x
    layout(root)

    max_depth = -min(y for _, y in pos.values())
    fig, ax = plt.subplots(figsize=(max(5, counter[0] * 2.2), max(2.5, (max_depth + 1) * 1.3)))

    def colour(n):
        if n.op in TEMPORAL: return "#cfe8ff"
        #if n.op in (Operation.ALWAYS, Operation.EVENT, Operation.UNTIL): return "#cfe8ff"   # temporal
        if n.op in (Operation.PRED, Operation.BOOL):                      return "#d9f2d9"   # leaves
        return "#ffe5b4"                                                                      # logical

    def draw(n):
        x, y = pos[id(n)]
        for c in kids(n):
            cx, cy = pos[id(c)]
            ax.plot([x, cx], [y, cy], color="gray", zorder=1)
            draw(c)
        ax.text(x, y, label(n), ha="center", va="center", fontsize=10, zorder=2,
                bbox=dict(boxstyle="round,pad=0.35", fc=colour(n), ec="black"))
    draw(root)

    ax.set_xlim(-0.7, max(counter[0] - 1, 0) + 0.7)
    ax.set_ylim(-max_depth - 0.6, 0.6)
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=10)
    plt.show()