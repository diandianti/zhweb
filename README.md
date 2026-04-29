# 典语言

用中文网络流行词写代码的 Brainfuck 方言。

```
『你好，典语言！』【10】绷
```

## 指令集

| 典语言 | Brainfuck | 含义 |
|--------|-----------|------|
| `赢` | `+` | 当前单元 +1 |
| `麻` | `-` | 当前单元 -1 |
| `典` | `>` | 指针右移 |
| `孝` | `<` | 指针左移 |
| `急` | `[` | 若当前值为 0，跳至配对的乐之后 |
| `乐` | `]` | 若当前值非 0，跳回配对的急 |
| `绷` | `.` | 输出当前单元对应的 Unicode 字符 |
| `《》` | `,` | 读入一个 Unicode 字符到当前单元 |

内存单元存储 Unicode 码点（0 ~ 1114111），天然支持全部汉字和 Emoji。

## 语法糖

编译期展开，不改变图灵机语义。

| 语法 | 含义 |
|------|------|
| `『文本』` | 依次输出字符串内每个字符 |
| `「字」` | 设置当前单元为该字的码点并输出 |
| `「」` | 将当前单元清零（等价于 `急麻乐`） |
| `【N】` | 将当前单元设为整数 N，支持全角数字 |

## 快速上手

```bash
# 运行示例
python dian_lang.py examples/hello.dian
python dian_lang.py examples/ni_hao.dian

# 管道输入（cat 程序）
echo "你好世界" | python dian_lang.py examples/cat.dian

# 交互式 REPL
python dian_lang.py
```

REPL 支持 `--ast 代码` 查看语法树，`--bf 代码` 直接执行 Brainfuck，`:q` 退出。

## CLI 选项

```
python dian_lang.py [选项] [文件]

--ast            显示 AST 而非执行
--dump-tokens    显示 Token 流
--bf-to-dian <f> 将 Brainfuck 转译为典语言
--dian-to-bf <f> 将典语言转译为 Brainfuck
-v, --version    显示版本
-h, --help       显示帮助
```

## 示例

**Hello, World!**（ASCII，`hello.dian`）
```
典赢赢赢赢赢赢赢赢急孝赢赢赢赢赢赢赢赢赢典麻乐孝绷
赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢赢绷
...
```

**你好世界**（Unicode，`ni_hao.dian`）
```
使用乘法循环快速爬升到汉字码点（20320+），配合差值跳转到下一个字：
典赢赢...赢(127个)
急
孝赢赢...赢(160个)典麻
乐
孝绷
...
```

**语法糖**（`sugar.dian`）
```
『你好，典语言！』【10】绷
「赢」「！」【10】绷
赢赢赢...赢「」【33】绷
```

## 运行测试

```bash
python test_dian_lang.py
```

40 个测试，覆盖词法、语法、解释执行、语法糖、转译器。
