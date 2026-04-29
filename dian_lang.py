#!/usr/bin/env python3
"""
典语言 (Diǎn Language) v0.2.0 — 中文网络梗 Brainfuck 方言
类 Brainfuck 图灵完备编程语言，使用中文网络流行词作为指令集。

原始指令集：
  赢  当前单元 +1                    (Brainfuck: +)
  麻  当前单元 -1                    (Brainfuck: -)
  典  指针右移                       (Brainfuck: >)
  孝  指针左移                       (Brainfuck: <)
  急  若当前值为0，跳至配对'乐'之后  (Brainfuck: [)
  乐  若当前值非0，跳回配对'急'      (Brainfuck: ])
  绷  输出当前单元 Unicode 字符      (Brainfuck: .)
  《》读入一个 Unicode 字符到当前单元 (Brainfuck: ,)

中文语法糖（编译期宏展开）：
  「字」  设置当前单元为该字的 Unicode 码点并输出（清零+累加+绷）
  「」    将当前单元清零
  【N】   设置当前单元为整数 N（0~1114111），支持全角数字
  『文本』 依次输出字符串内每个 Unicode 字符

内存单元存储 Unicode 码点（0 ~ sys.maxunicode），支持中文及全部 Unicode。
赢/麻 对 sys.maxunicode+1 取模，使码点在合法范围内循环。
"""

import sys
from dataclasses import dataclass, field
from typing import Optional

__version__ = "0.2.0"

_CODEPOINT_MOD = sys.maxunicode + 1  # Unicode 码点循环模数（1114112）

# Brainfuck 指令 ↔ 典语言 指令映射
_BF_TO_DIAN = {
    '+': '赢',
    '-': '麻',
    '>': '典',
    '<': '孝',
    '[': '急',
    ']': '乐',
    '.': '绷',
    ',': '《》',
}
_DIAN_TO_BF = {v: k for k, v in _BF_TO_DIAN.items()}


# ---------------------------------------------------------------------------
# AST 节点定义
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """AST 基类"""
    pass


@dataclass
class ProgramNode(Node):
    """程序根节点，包含指令序列"""
    body: list[Node] = field(default_factory=list)


@dataclass
class IncrNode(Node):
    """赢：当前单元 +count（折叠后可 >1）"""
    count: int = 1


@dataclass
class DecrNode(Node):
    """麻：当前单元 -count（折叠后可 >1）"""
    count: int = 1


@dataclass
class MoveRightNode(Node):
    """典：指针右移 count 步"""
    count: int = 1


@dataclass
class MoveLeftNode(Node):
    """孝：指针左移 count 步"""
    count: int = 1


@dataclass
class LoopNode(Node):
    """急...乐：循环块，当前值非0时重复执行"""
    body: list[Node] = field(default_factory=list)


@dataclass
class OutputNode(Node):
    """绷：输出当前单元 Unicode 字符"""
    pass


@dataclass
class InputNode(Node):
    """《》：读入一个 Unicode 字符到当前单元"""
    pass


# ---------------------------------------------------------------------------
# 词法分析器 (Lexer)
# ---------------------------------------------------------------------------

class LexError(Exception):
    def __init__(self, msg: str, pos: int, line: int = 0, col: int = 0):
        loc = f"第{line}行第{col}列" if line else f"位置{pos}"
        super().__init__(f"词法错误 {loc}: {msg}")
        self.pos = pos
        self.line = line
        self.col = col


def _expand_set_cell(target_cp: int, pos: int, line: int, col: int) -> list[tuple[str, int, int, int]]:
    """
    将「字」或【N】展开为「先清零，再累加到目标码点」的 token 序列。
    清零惯用法：急麻乐  （当前值非零则 -1，直到为零）
    再用赢*n 设置目标值。
    注意：清零+累加 的完整模式会由 _fold 在 parse 阶段折叠。
    """
    toks: list[tuple[str, int, int, int]] = []
    # 清零：急麻乐
    toks.append(('急', pos, line, col))
    toks.append(('麻', pos, line, col))
    toks.append(('乐', pos, line, col))
    # 累加到目标码点
    for _ in range(target_cp):
        toks.append(('赢', pos, line, col))
    return toks


def tokenize(source: str) -> list[tuple[str, int, int, int]]:
    """
    将源码转换为 token 列表。
    token 格式：(token_type, byte_pos, line, col)
    token_type 取值：赢 麻 典 孝 急 乐 绷 《》

    支持以下语法糖（编译期展开）：
      「字」   将当前单元设为该字的 Unicode 码点并输出，等价于清零+累加+绷
               若「」内为空则仅清零（将单元置0）
      【N】    将当前单元设为十进制整数 N（0~1114111），等价于清零+赢*N
      『文本』  依次输出引号内每个 Unicode 字符（字符串字面量输出）

    忽略所有其他字符（视为注释）。
    """
    tokens: list[tuple[str, int, int, int]] = []
    i = 0
    n = len(source)
    line = 1
    col = 1

    while i < n:
        ch = source[i]
        if ch == '\n':
            line += 1
            col = 1
            i += 1
            continue

        # ── 语法糖：「字」── 设置当前单元为该字的码点并输出
        if ch == '「':
            j = i + 1
            content_chars = []
            while j < n and source[j] != '」':
                if source[j] == '\n':
                    line += 1
                    col = 1
                content_chars.append(source[j])
                j += 1
            if j >= n:
                raise LexError("「 未找到配对的 」", i, line, col)
            content = ''.join(content_chars)
            if len(content) == 0:
                # 「」= 清零
                tokens.extend(_expand_set_cell(0, i, line, col))
            elif len(content) == 1:
                # 「字」= 设置码点 + 输出
                tokens.extend(_expand_set_cell(ord(content), i, line, col))
                tokens.append(('绷', i, line, col))
            else:
                raise LexError("「」内只能含零或一个字符（多字符输出请用『』）", i, line, col)
            col += j - i + 1
            i = j + 1
            continue

        # ── 语法糖：【N】── 设置当前单元为十进制整数 N
        if ch == '【':
            j = i + 1
            digits = []
            while j < n and source[j] != '】':
                if source[j] == '\n':
                    raise LexError("【】内不能换行", i, line, col)
                digits.append(source[j])
                j += 1
            if j >= n:
                raise LexError("【 未找到配对的 】", i, line, col)
            num_str = ''.join(digits).strip()
            # 支持中文数字简写：支持阿拉伯数字及全角数字
            num_str_norm = num_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
            try:
                value = int(num_str_norm)
            except ValueError:
                raise LexError(f"【】内须为整数，得到 {num_str!r}", i, line, col)
            if not (0 <= value <= sys.maxunicode):
                raise LexError(f"【】值须在 0~{sys.maxunicode} 范围内，得到 {value}", i, line, col)
            tokens.extend(_expand_set_cell(value, i, line, col))
            col += j - i + 1
            i = j + 1
            continue

        # ── 语法糖：『文本』── 依次输出字符串内所有字符
        if ch == '『':
            j = i + 1
            str_chars = []
            while j < n and source[j] != '』':
                if source[j] == '\n':
                    line += 1
                    col = 1
                str_chars.append(source[j])
                j += 1
            if j >= n:
                raise LexError("『 未找到配对的 』", i, line, col)
            prev_cp = 0
            for c in str_chars:
                cp = ord(c)
                delta = cp - prev_cp
                if delta > 0:
                    for _ in range(delta):
                        tokens.append(('赢', i, line, col))
                elif delta < 0:
                    for _ in range(-delta):
                        tokens.append(('麻', i, line, col))
                tokens.append(('绷', i, line, col))
                prev_cp = cp
            col += j - i + 1
            i = j + 1
            continue

        # ── 原始指令 ──
        if ch in ('赢', '麻', '典', '孝', '急', '乐', '绷'):
            tokens.append((ch, i, line, col))
            col += 1
            i += 1
        elif ch == '《':
            # 《》是双字符指令，中间允许有空白/注释
            j = i + 1
            while j < n and source[j] != '》':
                if source[j] == '\n':
                    line += 1
                    col = 1
                j += 1
            if j >= n:
                raise LexError("《 未找到配对的 》", i, line, col)
            tokens.append(('《》', i, line, col))
            col += 2
            i = j + 1
        else:
            col += 1
            i += 1
    return tokens


# ---------------------------------------------------------------------------
# 语法分析器 (Parser)
# ---------------------------------------------------------------------------

class ParseError(Exception):
    def __init__(self, msg: str, pos: int, line: int = 0, col: int = 0):
        loc = f"第{line}行第{col}列" if line else f"位置{pos}"
        super().__init__(f"语法错误 {loc}: {msg}")
        self.pos = pos
        self.line = line
        self.col = col


def _fold(nodes: list[Node]) -> list[Node]:
    """Run-Length 折叠：将连续同类可数节点合并，提升执行效率。"""
    if not nodes:
        return nodes
    result: list[Node] = []
    for node in nodes:
        if result and type(result[-1]) is type(node) and isinstance(node, (IncrNode, DecrNode, MoveRightNode, MoveLeftNode)):
            result[-1].count += 1
        else:
            result.append(node)
    return result


def parse(tokens: list[tuple[str, int, int, int]]) -> ProgramNode:
    """将 token 列表解析为 AST（含 RLE 折叠优化）"""
    pos = 0

    def parse_body(end_token: Optional[str] = None) -> list[Node]:
        nonlocal pos
        nodes: list[Node] = []
        while pos < len(tokens):
            tok, tok_pos, tok_line, tok_col = tokens[pos]
            if tok == end_token:
                return _fold(nodes)
            pos += 1
            if tok == '赢':
                nodes.append(IncrNode())
            elif tok == '麻':
                nodes.append(DecrNode())
            elif tok == '典':
                nodes.append(MoveRightNode())
            elif tok == '孝':
                nodes.append(MoveLeftNode())
            elif tok == '绷':
                nodes.append(OutputNode())
            elif tok == '《》':
                nodes.append(InputNode())
            elif tok == '急':
                body = parse_body('乐')
                if pos >= len(tokens):
                    raise ParseError("急 未找到配对的 乐", tok_pos, tok_line, tok_col)
                pos += 1  # 消费 乐
                nodes.append(LoopNode(body=body))
            elif tok == '乐':
                raise ParseError("乐 没有配对的 急", tok_pos, tok_line, tok_col)
        if end_token is not None:
            raise ParseError(f"缺少结束符 {end_token}", len(tokens))
        return _fold(nodes)

    body = parse_body()
    return ProgramNode(body=body)


# ---------------------------------------------------------------------------
# 解释器 (Interpreter)
# ---------------------------------------------------------------------------

class DianRuntimeError(Exception):
    def __init__(self, msg: str):
        super().__init__(f"运行时错误: {msg}")


MEMORY_SIZE = 30000


class Interpreter:
    def __init__(self, input_stream=None, output_stream=None):
        self.memory: list[int] = [0] * MEMORY_SIZE  # 存储 Unicode 码点
        self.pointer = 0
        self.input_stream = input_stream or sys.stdin
        self.output_stream = output_stream or sys.stdout

    def run(self, node: Node):
        method = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method, self._visit_unknown)
        return visitor(node)

    def _visit_ProgramNode(self, node: ProgramNode):
        for child in node.body:
            self.run(child)

    def _visit_IncrNode(self, node: IncrNode):
        self.memory[self.pointer] = (self.memory[self.pointer] + node.count) % _CODEPOINT_MOD

    def _visit_DecrNode(self, node: DecrNode):
        self.memory[self.pointer] = (self.memory[self.pointer] - node.count) % _CODEPOINT_MOD

    def _visit_MoveRightNode(self, node: MoveRightNode):
        self.pointer += node.count
        if self.pointer >= MEMORY_SIZE:
            raise DianRuntimeError(f"内存指针越界（右移至 {self.pointer}，上限 {MEMORY_SIZE - 1}）")

    def _visit_MoveLeftNode(self, node: MoveLeftNode):
        self.pointer -= node.count
        if self.pointer < 0:
            raise DianRuntimeError(f"内存指针越界（左移至 {self.pointer}）")

    def _visit_OutputNode(self, node: OutputNode):
        char = chr(self.memory[self.pointer])
        self.output_stream.write(char)
        self.output_stream.flush()

    def _visit_InputNode(self, node: InputNode):
        ch = self.input_stream.read(1)
        if ch:
            self.memory[self.pointer] = ord(ch[0])
        else:
            self.memory[self.pointer] = 0  # EOF → 0

    def _visit_LoopNode(self, node: LoopNode):
        while self.memory[self.pointer] != 0:
            for child in node.body:
                self.run(child)

    def _visit_unknown(self, node: Node):
        raise DianRuntimeError(f"未知节点类型: {type(node).__name__}")


# ---------------------------------------------------------------------------
# 转译器 (Transpiler)
# ---------------------------------------------------------------------------

def bf_to_dian(bf_source: str) -> str:
    """将 Brainfuck 源码转译为典语言源码（忽略非指令字符）。"""
    parts = []
    for ch in bf_source:
        if ch in _BF_TO_DIAN:
            parts.append(_BF_TO_DIAN[ch])
    return ''.join(parts)


def dian_to_bf(dian_source: str) -> str:
    """将典语言源码转译为 Brainfuck 源码（忽略非指令字符）。"""
    parts = []
    i = 0
    n = len(dian_source)
    while i < n:
        ch = dian_source[i]
        if ch == '《':
            j = i + 1
            while j < n and dian_source[j] != '》':
                j += 1
            parts.append(',')
            i = j + 1
        elif ch in _DIAN_TO_BF:
            parts.append(_DIAN_TO_BF[ch])
            i += 1
        else:
            i += 1
    return ''.join(parts)


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

def compile_source(source: str) -> ProgramNode:
    """将典语言源码编译为 AST"""
    tokens = tokenize(source)
    return parse(tokens)


def run_source(source: str, input_stream=None, output_stream=None):
    """编译并执行典语言源码"""
    ast = compile_source(source)
    interp = Interpreter(input_stream=input_stream, output_stream=output_stream)
    interp.run(ast)


def ast_to_str(node: Node, indent: int = 0) -> str:
    """将 AST 格式化为可读字符串（用于调试）"""
    pad = "  " * indent
    if isinstance(node, ProgramNode):
        children = "\n".join(ast_to_str(c, indent + 1) for c in node.body)
        return f"{pad}程序\n{children}" if children else f"{pad}程序（空）"
    elif isinstance(node, LoopNode):
        children = "\n".join(ast_to_str(c, indent + 1) for c in node.body)
        return f"{pad}循环急乐\n{children}"
    else:
        names = {
            IncrNode:      lambda n: f"赢（+{n.count}）",
            DecrNode:      lambda n: f"麻（-{n.count}）",
            MoveRightNode: lambda n: f"典（右移{n.count}）",
            MoveLeftNode:  lambda n: f"孝（左移{n.count}）",
            OutputNode:    lambda n: "绷（输出）",
            InputNode:     lambda n: "《》（输入）",
        }
        fn = names.get(type(node))
        return f"{pad}{fn(node) if fn else str(node)}"


def dump_tokens(source: str) -> str:
    """将源码的 token 流格式化为可读字符串（用于调试）"""
    tokens = tokenize(source)
    lines = []
    for tok, pos, line, col in tokens:
        lines.append(f"  [{pos:4d}] 第{line}行第{col}列  {tok}")
    return "Token 流：\n" + "\n".join(lines) if lines else "Token 流：（空）"


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

_HELP = """\
典语言 (Diǎn Language) v{ver} — 中文网络梗 Brainfuck 方言

用法：
  python dian_lang.py [选项] [文件]
  python dian_lang.py              # 无参数：进入 REPL

选项：
  -h, --help            显示此帮助信息
  -v, --version         显示版本号
  --ast                 显示 AST 而非执行程序
  --dump-tokens         显示 Token 流而非执行程序
  --bf-to-dian <文件>   将 Brainfuck 程序转译为典语言
  --dian-to-bf <文件>   将典语言程序转译为 Brainfuck

原始指令集：
  赢  +1   麻  -1   典  右移   孝  左移
  急  [    乐  ]    绷  输出   《》输入

中文语法糖（编译期展开）：
  「字」   设置当前单元为该字的 Unicode 码点并输出（清零+累加+绷）
  「」     仅将当前单元清零（急麻乐 惯用法的简写）
  【N】    设置当前单元为整数 N，支持全角数字（清零+赢*N）
  『文本』  依次输出引号内每个 Unicode 字符（差值累加，不改变内存结构）

语法糖示例：
  「你」          输出"你"（等价于 急麻乐 赢赢...赢(20320次) 绷）
  【65】绷         输出"A"（ASCII 65）
  『你好世界』      依次输出四个汉字

REPL 特殊命令：
  --ast 代码     显示代码的 AST
  --tokens 代码  显示代码的 Token 流
  --bf 代码      将 Brainfuck 代码转译并执行
  :q / quit      退出

示例：
  python dian_lang.py examples/hello.dian
  python dian_lang.py examples/ni_hao.dian
  echo "你好" | python dian_lang.py examples/cat.dian
  python dian_lang.py --bf-to-dian hello.bf
""".format(ver=__version__)


def main():
    args = sys.argv[1:]

    # ---------- 帮助 / 版本 ----------
    if not args or args[0] in ('-h', '--help'):
        if not args:
            # 无参数：进入 REPL
            pass
        else:
            print(_HELP)
            return

    if args and args[0] in ('-v', '--version'):
        print(f"典语言 v{__version__}")
        return

    # ---------- 转译模式 ----------
    if args and args[0] == '--bf-to-dian':
        if len(args) < 2:
            print("用法：python dian_lang.py --bf-to-dian <bf文件>", file=sys.stderr)
            sys.exit(1)
        try:
            src = open(args[1], encoding='utf-8').read()
        except FileNotFoundError:
            print(f"错误：找不到文件 {args[1]!r}", file=sys.stderr)
            sys.exit(1)
        print(bf_to_dian(src))
        return

    if args and args[0] == '--dian-to-bf':
        if len(args) < 2:
            print("用法：python dian_lang.py --dian-to-bf <dian文件>", file=sys.stderr)
            sys.exit(1)
        try:
            src = open(args[1], encoding='utf-8').read()
        except FileNotFoundError:
            print(f"错误：找不到文件 {args[1]!r}", file=sys.stderr)
            sys.exit(1)
        print(dian_to_bf(src))
        return

    # ---------- REPL 模式 ----------
    if not args:
        print(f"典语言 v{__version__} REPL（Ctrl+D 退出，-h 查看帮助）")
        print("  --ast 代码     显示 AST")
        print("  --tokens 代码  显示 Token 流")
        print("  --bf 代码      执行 Brainfuck 代码")
        while True:
            try:
                line = input(">>> ")
            except EOFError:
                print()
                break
            line = line.strip()
            if not line or line in (':q', 'quit', 'exit'):
                break
            try:
                if line.startswith('--ast'):
                    code = line[5:].strip()
                    print(ast_to_str(compile_source(code)))
                elif line.startswith('--tokens'):
                    code = line[8:].strip()
                    print(dump_tokens(code))
                elif line.startswith('--bf '):
                    code = bf_to_dian(line[4:].strip())
                    interp = Interpreter()
                    interp.run(compile_source(code))
                    print()
                else:
                    interp = Interpreter()
                    interp.run(compile_source(line))
                    print()
            except Exception as e:
                print(f"错误：{e}", file=sys.stderr)
        return

    # ---------- 文件执行模式 ----------
    # 从参数中提取标志和文件路径
    flags = {a for a in args if a.startswith('--')}
    files = [a for a in args if not a.startswith('--') and not a.startswith('-')]

    show_ast = '--ast' in flags
    show_tokens = '--dump-tokens' in flags

    if not files:
        print("错误：请指定要执行的文件，或不带参数进入 REPL", file=sys.stderr)
        print("运行 python dian_lang.py --help 查看帮助", file=sys.stderr)
        sys.exit(1)

    filepath = files[0]
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"错误：找不到文件 {filepath!r}", file=sys.stderr)
        sys.exit(1)

    try:
        if show_tokens:
            print(dump_tokens(source))
            return
        ast = compile_source(source)
        if show_ast:
            print(ast_to_str(ast))
        else:
            interp = Interpreter()
            interp.run(ast)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
