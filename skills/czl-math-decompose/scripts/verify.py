#!/usr/bin/env python3
"""verify.py - the numeric half of "回头验" (step 5 of the decomposition routine).

A student's answer is a claim. This script tests the claim against numbers
instead of against the answer key, which is the habit we actually want to build.

It is deliberately narrow: one expression of one variable, evaluated at points,
checked for zeros, checked for monotonicity, or scanned for extremes. No CAS,
no symbolic algebra, no dependency outside the standard library.

Expression syntax
-----------------
    x^2 - 3*x + 2        ^ is power, * is required between factors
    sin(x) + ln(x)       allowed: sin cos tan asin acos atan sqrt ln log exp abs
    e, pi                constants
Everything is evaluated with a whitelisted AST walker - never eval().

Usage
-----
    # 代值验: what is f(1.5)?
    python verify.py --expr "x^2-3*x+2" --at 1.5

    # 代值验, 对比学生答案: is f(2) == 0?
    python verify.py --expr "x^2-3*x+2" --zero 1,2

    # 边界验: is f increasing on (0,1)?
    python verify.py --expr "x^3-3*x" --mono dec --on -1,1

    # 范围验: sample min/max on an interval
    python verify.py --expr "x^2-2*x" --minmax --on 0,3

Exit code: 0 all checks passed, 1 a check failed, 2 bad input.
"""

import argparse
import ast
import math
import sys

ALLOWED_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sqrt": math.sqrt, "ln": math.log, "log": math.log10,
    "exp": math.exp, "abs": abs,
}
CONSTANTS = {"e": math.e, "pi": math.pi}

BIN_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b,
    ast.Mod: lambda a, b: a % b,
}
UNARY_OPS = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}


class Expr:
    """A parsed, whitelisted arithmetic expression in one variable."""

    def __init__(self, text, var="x"):
        self.text = text
        self.var = var
        normalised = text.replace("^", "**")
        try:
            self.tree = ast.parse(normalised, mode="eval").body
        except SyntaxError as exc:
            raise ValueError("cannot parse %r: %s" % (text, exc.msg))

    def __call__(self, value):
        return self._eval(self.tree, value)

    def _eval(self, node, value):
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError("only numeric constants allowed")
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id == self.var:
                return float(value)
            if node.id in CONSTANTS:
                return CONSTANTS[node.id]
            raise ValueError("unknown symbol %r (allowed: %s, %s)"
                             % (node.id, self.var, ", ".join(CONSTANTS)))
        if isinstance(node, ast.BinOp):
            op = BIN_OPS.get(type(node.op))
            if op is None:
                raise ValueError("operator %s not allowed" % type(node.op).__name__)
            return op(self._eval(node.left, value), self._eval(node.right, value))
        if isinstance(node, ast.UnaryOp):
            op = UNARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError("unary %s not allowed" % type(node.op).__name__)
            return op(self._eval(node.operand, value))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCS:
                raise ValueError("function not allowed")
            if len(node.args) != 1 or node.keywords:
                raise ValueError("%s takes exactly one argument" % node.func.id)
            return ALLOWED_FUNCS[node.func.id](self._eval(node.args[0], value))
        raise ValueError("expression too complex: %s" % type(node).__name__)


def parse_points(text):
    return [float(p) for p in text.replace(" ", "").split(",") if p]


def fmt(v):
    if abs(v - round(v)) < 1e-12:
        return str(int(round(v)))
    return "%.6g" % v


def normalise_argv(argv):
    """Let negative numbers be values: '--on -1,1' instead of '--on=-1,1'."""
    out = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if (tok in ("--on", "--at", "--zero") and i + 1 < len(argv)
                and argv[i + 1].lstrip().startswith("-")):
            out.append("%s=%s" % (tok, argv[i + 1]))
            i += 2
            continue
        out.append(tok)
        i += 1
    return out


def main(argv=None):
    argv = normalise_argv(list(sys.argv[1:] if argv is None else argv))
    ap = argparse.ArgumentParser(description="Numeric checks for a claimed answer.")
    ap.add_argument("--expr", required=True, help="expression in x, e.g. \"x^2-3*x+2\"")
    ap.add_argument("--var", default="x")
    ap.add_argument("--at", help="comma separated x values to evaluate")
    ap.add_argument("--zero", help="comma separated values that should be roots")
    ap.add_argument("--mono", choices=["inc", "dec"], help="monotonicity claim to test")
    ap.add_argument("--on", help="interval a,b for --mono / --minmax")
    ap.add_argument("--minmax", action="store_true", help="sample extremes on --on")
    ap.add_argument("--samples", type=int, default=400)
    ap.add_argument("--tol", type=float, default=1e-6)
    args = ap.parse_args(argv)

    try:
        f = Expr(args.expr, args.var)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    if not any([args.at, args.zero, args.mono, args.minmax]):
        print("ERROR: give at least one check (--at / --zero / --mono / --minmax)",
              file=sys.stderr)
        return 2

    failed = False
    print("f(%s) = %s" % (args.var, args.expr))

    if args.at:
        for p in parse_points(args.at):
            try:
                print("  代值验  %s = %s  ->  f = %s"
                      % (args.var, fmt(p), fmt(f(p))))
            except (ValueError, ZeroDivisionError) as exc:
                failed = True
                print("  代值验  %s = %s  ->  无定义（%s）" % (args.var, fmt(p), exc))

    if args.zero:
        for p in parse_points(args.zero):
            try:
                v = f(p)
            except (ValueError, ZeroDivisionError) as exc:
                failed = True
                print("  零点验  %s = %s  ->  FAIL 无定义（%s）" % (args.var, fmt(p), exc))
                continue
            ok = abs(v) <= args.tol
            failed |= not ok
            print("  零点验  %s = %s  ->  f = %s  ->  %s"
                  % (args.var, fmt(p), fmt(v), "PASS" if ok else "FAIL 不是零点"))

    if args.mono or args.minmax:
        if not args.on:
            print("ERROR: --mono / --minmax need --on a,b", file=sys.stderr)
            return 2
        a, b = parse_points(args.on)[:2]
        if a >= b:
            print("ERROR: --on needs a < b", file=sys.stderr)
            return 2
        step = (b - a) / args.samples
        xs = [a + i * step for i in range(args.samples + 1)]
        try:
            ys = [f(v) for v in xs]
        except (ValueError, ZeroDivisionError) as exc:
            print("ERROR: undefined inside [%s, %s]: %s" % (fmt(a), fmt(b), exc),
                  file=sys.stderr)
            return 2

        if args.minmax:
            imin = min(range(len(ys)), key=lambda i: ys[i])
            imax = max(range(len(ys)), key=lambda i: ys[i])
            print("  范围验  [%s, %s] 采样 %d 点：min ≈ %s (at x=%s)，max ≈ %s (at x=%s)"
                  % (fmt(a), fmt(b), args.samples, fmt(ys[imin]), fmt(xs[imin]),
                     fmt(ys[imax]), fmt(xs[imax])))

        if args.mono:
            diffs = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
            if args.mono == "inc":
                bad = [i for i, d in enumerate(diffs) if d < -1e-9]
            else:
                bad = [i for i, d in enumerate(diffs) if d > 1e-9]
            word = "递增" if args.mono == "inc" else "递减"
            if bad:
                failed = True
                i = bad[0]
                print("  单调验  [%s, %s] 上不是单调%s -> FAIL，"
                      "在 x≈%s 附近掉头（f=%s -> %s）"
                      % (fmt(a), fmt(b), word, fmt(xs[i]), fmt(ys[i]),
                         fmt(ys[i + 1])))
            else:
                print("  单调验  [%s, %s] 上%s -> PASS（采样 %d 点，无掉头）"
                      % (fmt(a), fmt(b), word, args.samples))

    print("结论：%s" % ("全部通过" if not failed else "存在未通过项，答案需要重做"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
