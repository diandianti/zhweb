#!/usr/bin/env python3
"""典语言 测试套件"""

import io
import sys
import unittest

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import dian_lang
from dian_lang import (
    LexError, ParseError, DianRuntimeError,
    tokenize, compile_source, run_source,
    bf_to_dian, dian_to_bf,
)


def run(source: str, stdin: str = '') -> str:
    out = io.StringIO()
    run_source(source, input_stream=io.StringIO(stdin), output_stream=out)
    return out.getvalue()


class TestTokenizer(unittest.TestCase):
    def _types(self, source):
        return [t for t, *_ in tokenize(source)]

    def test_basic_tokens(self):
        self.assertEqual(self._types('赢麻典孝急乐绷'), ['赢', '麻', '典', '孝', '急', '乐', '绷'])

    def test_input_token(self):
        self.assertEqual(self._types('《》'), ['《》'])

    def test_ignores_comments(self):
        self.assertEqual(self._types('赢 注释 麻'), ['赢', '麻'])

    def test_line_col(self):
        tokens = tokenize('赢\n麻')
        self.assertEqual(tokens[0][2:], (1, 1))
        self.assertEqual(tokens[1][2:], (2, 1))

    def test_unmatched_open_angle(self):
        with self.assertRaises(LexError):
            tokenize('《没有关')

    def test_sugar_string_literal(self):
        toks = self._types('『AB』')
        self.assertEqual(toks, ['赢'] * 65 + ['绷'] + ['赢'] * 1 + ['绷'])

    def test_sugar_set_int(self):
        toks = self._types('【3】')
        self.assertEqual(toks, ['急', '麻', '乐', '赢', '赢', '赢'])

    def test_sugar_set_int_fullwidth(self):
        self.assertEqual(self._types('【３】'), self._types('【3】'))

    def test_sugar_single_char(self):
        toks = self._types('「A」')
        self.assertIn('绷', toks)

    def test_sugar_clear_cell(self):
        self.assertEqual(self._types('「」'), ['急', '麻', '乐'])

    def test_sugar_string_error_unclosed(self):
        with self.assertRaises(LexError):
            tokenize('『未关闭')

    def test_sugar_char_error_multi(self):
        with self.assertRaises(LexError):
            tokenize('「两字」')

    def test_sugar_int_error_invalid(self):
        with self.assertRaises(LexError):
            tokenize('【abc】')

    def test_sugar_int_error_out_of_range(self):
        with self.assertRaises(LexError):
            tokenize('【9999999】')


class TestParser(unittest.TestCase):
    def test_empty_program(self):
        ast = compile_source('')
        self.assertEqual(ast.body, [])

    def test_loop_node(self):
        from dian_lang import LoopNode, IncrNode
        ast = compile_source('急赢乐')
        self.assertEqual(len(ast.body), 1)
        self.assertIsInstance(ast.body[0], LoopNode)

    def test_unmatched_open_loop(self):
        with self.assertRaises(ParseError):
            compile_source('急赢赢')

    def test_unmatched_close_loop(self):
        with self.assertRaises(ParseError):
            compile_source('赢乐')

    def test_rle_fold(self):
        from dian_lang import IncrNode
        ast = compile_source('赢赢赢赢赢')
        self.assertEqual(len(ast.body), 1)
        self.assertIsInstance(ast.body[0], IncrNode)
        self.assertEqual(ast.body[0].count, 5)

    def test_rle_no_fold_across_types(self):
        from dian_lang import IncrNode, DecrNode
        ast = compile_source('赢赢麻麻')
        self.assertEqual(len(ast.body), 2)


class TestInterpreter(unittest.TestCase):
    def test_hello_ascii(self):
        # 输出 'A' (65)
        self.assertEqual(run('赢' * 65 + '绷'), 'A')

    def test_hello_world_file(self):
        with open('examples/hello.dian', encoding='utf-8') as f:
            src = f.read()
        self.assertEqual(run(src), 'Hello, World!\n')

    def test_cat(self):
        with open('examples/cat.dian', encoding='utf-8') as f:
            src = f.read()
        self.assertEqual(run(src, '你好'), '你好')

    def test_chinese_hello(self):
        with open('examples/ni_hao.dian', encoding='utf-8') as f:
            src = f.read()
        self.assertEqual(run(src), '你好世界\n')

    def test_sugar_string(self):
        self.assertEqual(run('『Hello』'), 'Hello')

    def test_sugar_chinese_string(self):
        self.assertEqual(run('『你好世界』'), '你好世界')

    def test_sugar_set_int(self):
        self.assertEqual(run('【65】绷'), 'A')

    def test_sugar_set_int_resets(self):
        # 赢*100 then 【65】 should give 'A', not chr(165)
        self.assertEqual(run('赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢【65】绷'), 'A')

    def test_sugar_clear(self):
        self.assertEqual(run('赢赢赢赢赢「」赢绷'), chr(1))

    def test_sugar_single_char_output(self):
        self.assertEqual(run('「你」'), '你')

    def test_loop_basic(self):
        # cell[0]=5, cell[1]=5, 循环5次 cell[0]+=1 => cell[0]=10 => chr(10)='\n'
        self.assertEqual(run('赢赢赢赢赢典赢赢赢赢赢急孝赢典麻乐孝绷'), chr(10))

    def test_memory_boundary_right(self):
        from dian_lang import DianRuntimeError
        with self.assertRaises(DianRuntimeError):
            run('典' * 30001)

    def test_memory_boundary_left(self):
        from dian_lang import DianRuntimeError
        with self.assertRaises(DianRuntimeError):
            run('孝')

    def test_unicode_wraparound(self):
        # maxunicode + 1 应回到 0
        run('赢' * (__import__('sys').maxunicode + 1))

    def test_input_eof(self):
        # EOF 时输入应设为 0
        out = io.StringIO()
        run_source('《》绷', input_stream=io.StringIO(''), output_stream=out)
        self.assertEqual(out.getvalue(), chr(0))


class TestTranspiler(unittest.TestCase):
    def test_bf_to_dian_basic(self):
        self.assertEqual(bf_to_dian('+'), '赢')
        self.assertEqual(bf_to_dian('-'), '麻')
        self.assertEqual(bf_to_dian('>'), '典')
        self.assertEqual(bf_to_dian('<'), '孝')
        self.assertEqual(bf_to_dian('['), '急')
        self.assertEqual(bf_to_dian(']'), '乐')
        self.assertEqual(bf_to_dian('.'), '绷')
        self.assertEqual(bf_to_dian(','), '《》')

    def test_dian_to_bf_basic(self):
        self.assertEqual(dian_to_bf('赢'), '+')
        self.assertEqual(dian_to_bf('麻'), '-')
        self.assertEqual(dian_to_bf('《》'), ',')

    def test_roundtrip(self):
        bf = '+++[->+<]>.'
        self.assertEqual(dian_to_bf(bf_to_dian(bf)), bf)

    def test_bf_hello_world(self):
        bf = (
            '++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]'
            '>>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++.'
        )
        dian = bf_to_dian(bf)
        self.assertEqual(run(dian), 'Hello World!\n')

    def test_ignore_non_instructions(self):
        self.assertEqual(bf_to_dian('+ comment - more'), '赢麻')
        self.assertEqual(dian_to_bf('赢 注释 麻'), '+-')


if __name__ == '__main__':
    unittest.main(verbosity=2)
