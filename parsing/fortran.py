from . import alphanumeric, letter, digit, one_of, whitespace, none_of
from . import Failure, succeed, matches, Success, spaces, wildcard
from . import join, exact, token, satisfies, singleton, EOF, parser, concat

from argparse import ArgumentParser


def keyword(string):
    return token(exact(string, ignore_case=True))


class Token(object):
    def __init__(self, tag, value):
        self.value = value
        self.tag = tag

    def __repr__(self):
        return self.tag + "{" + self.value + "}"


def tag_token(tag):
    def inner(value):
        return Token(tag, value)
    return inner


class Grammar(object):
    continuation_column = 5
    margin_column = continuation_column + 1

    statements = {}
    statements["control nonblock"] = [['go', 'to'], ['call'], ['return'],
                                      ['continue'], ['stop'], ['pause']]

    statements["control block"] = [['if'], ['else', 'if'],
                                   ['else'], ['end', 'if'], ['do'],
                                   ['end', 'do']]

    statements["control"] = (statements["control block"] +
                             statements["control nonblock"])

    statements["io"] = [['read'], ['write'], ['print'], ['rewind'],
                        ['backspace'], ['endfile'], ['open'], ['close'],
                        ['inquire']]

    statements["assign"] = [['assign']]

    statements["executable"] = (statements["control"] +
                                statements["assign"] + statements["io"])

    statements["type"] = [['integer'], ['real'], ['double', 'precision'],
                          ['complex'], ['logical'], ['character']]

    statements["specification"] = (statements["type"] +
                                   [['dimension'], ['common'],
                                    ['equivalence'], ['implicit'],
                                    ['parameter'], ['external'],
                                    ['intrinsic'], ['save']])

    statements["top level"] = [['program'], ['end', 'program'], ['function'],
                               ['end', 'function'], ['subroutine'],
                               ['end', 'subroutine'], ['block', 'data'],
                               ['end', 'block', 'data'], ['end']]

    statements["misc nonexec"] = [['entry'], ['data'], ['format']]

    statements["non-executable"] = (statements["specification"] +
                                    statements["misc nonexec"] +
                                    statements["top level"])

    # order is important here
    # because 'end' should come before 'end if' et cetera
    statements["all"] = (statements["executable"] +
                         statements["non-executable"])

    name = letter + alphanumeric.many() // join
    label = digit.between(1, 5) // join
    integer = (one_of("+-").optional() + +digit) // join
    logical = exact(".true.") | exact(".false.")
    char_segment = ((exact('"') + none_of('"').many() // join + exact('"')) |
                    (exact("'") + none_of("'").many() // join + exact("'")))

    character = (+char_segment) // join
    basic_real = (one_of("+-").optional() + +digit +
                  exact(".") // singleton + digit.many()) // join
    single_exponent = one_of("eE") + integer
    single = ((basic_real + single_exponent.optional() // join) |
              (integer + single_exponent))
    double_exponent = one_of("dD") + integer
    double = (basic_real | integer) + double_exponent
    real = double | single
    comment = exact("!") + none_of("\n").many() // join
    equals, plus, minus, times, slash = [exact(c) for c in "=+-*/"]
    lparen, rparen, dot, comma, dollar = [exact(c) for c in "().,$"]
    apostrophe, quote, colon, langle, rangle = [exact(c) for c in "'\":<>"]

    single_token = (character // tag_token("character") |
                    comment // tag_token("comment") |
                    logical // tag_token("logical") |
                    real // tag_token("real") |
                    integer // tag_token("integer") |
                    name // tag_token("name") |
                    equals // tag_token("equals") |
                    plus // tag_token("plus") |
                    minus // tag_token("minus") |
                    times // tag_token("times") |
                    slash // tag_token("slash") |
                    lparen // tag_token("lparen") |
                    rparen // tag_token("rparen") |
                    dot // tag_token("dot") |
                    comma // tag_token("comma") |
                    dollar // tag_token("dollar") |
                    apostrophe // tag_token("apostrophe") |
                    quote // tag_token("quote") |
                    colon // tag_token("colon") |
                    langle // tag_token("langle") |
                    rangle // tag_token("rangle") |
                    spaces // tag_token("whitespace") |
                    wildcard // tag_token("unknown"))

    tokenizer = (single_token).many()


def outer_block(statement):
    def inner(content):
        return OuterBlock(content, statement)
    return inner


class OuterBlock(object):
    def __init__(self, content, statement):
        self.content = content
        self.statement = statement

    def accept(self, visitor):
        return visitor.outer_block(self)

    def __repr__(self):
        return print_details(self)

    def __str__(self):
        return plain(self)


def inner_block(content):
    return InnerBlock(content)


class InnerBlock(object):
    def __init__(self, content):
        # this is a list of `LogicalLine`s
        self.content = content

        statements = Grammar.statements

        non_block_statements = (statements["io"] + statements["assign"] +
                                statements["specification"] +
                                statements["misc nonexec"] +
                                statements["control nonblock"])

        non_block = one_of_types(non_block_statements)

        do_statement = one_of_types([["do"]])
        end_do_statement = one_of_types([["end", "do"]])

        if_statement = one_of_types([["if"]])
        else_if_statement = one_of_types([["else", "if"]])
        else_statement = one_of_types([["else"]])
        end_if_statement = one_of_types([["end", "if"]])

        def new_style_if(ll):
            code = ll.code.lower()
            success = keyword("if").scan(code)
            rest = code[success.end:]
            # this is a hack that I am currently happy with
            return rest.find("then") != -1

        @parser
        def if_block(text, start):
            begin = (if_statement.guard(new_style_if, "new style if") //
                     singleton)
            inner = (non_block | do_block | if_block |
                     none_of_types([["end", "if"], ["else", "if"], ["else"]]))
            else_or_else_if = else_if_statement | else_statement

            def inner_block_or_empty(ls):
                if ls != []:
                    return [inner_block(ls)]
                else:
                    return []

            section = ((inner.many() // inner_block_or_empty) +
                       else_or_else_if.optional()).guard(lambda l: l != [],
                                                         "anything")
            sections = section.many() // concat

            end = (end_if_statement // singleton)

            result = (((begin + sections + end) // outer_block("if_block"))
                      .scan(text, start))

            return result

        def new_style_do(ll):
            return not matches(keyword("do") + token(Grammar.label),
                               ll.code.lower())

        @parser
        def do_block(text, start):
            begin = (do_statement.guard(new_style_do, "new style do") //
                     singleton)

            inner = ((non_block | do_block | if_block |
                      none_of_types([["end", "do"]]))
                     .many() // inner_block // singleton)
            end = end_do_statement // singleton

            return (((begin + inner + end) // outer_block("do_block"))
                    .scan(text, start))

        block_or_line = non_block | do_block | if_block | wildcard

        # this is a list of LogicalLines or OuterBlocks
        self.blocks = block_or_line.many().parse(content)

    def accept(self, visitor):
        return visitor.inner_block(self)

    def __repr__(self):
        return print_details(self)

    def __str__(self):
        return plain(self)


class RawLine(object):
    def __init__(self, line):
        self.original = line

        continuation_column = Grammar.continuation_column
        margin_column = Grammar.margin_column

        lowered = line.rstrip().lower()

        if matches(EOF | one_of("*c") | keyword("!"), lowered):
            self.type = "comment"
            return

        if len(lowered) > continuation_column:
            if matches(none_of("0 "), lowered, continuation_column):
                self.type = "continuation"
                assert len(lowered[:continuation_column].strip()) == 0
                self.code = line[margin_column:]
                self.cont = line[continuation_column:margin_column]
                self.tokens = Grammar.tokenizer.parse(self.code)
                return

        self.type = "initial"

        statement_label = lowered[:continuation_column]
        if len(statement_label.strip()) > 0:
            self.label = (token(Grammar.label) // int).parse(statement_label)

        self.code = line[margin_column:]
        self.tokens = Grammar.tokenizer.parse(self.code)

        def check(words):
            msg = succeed(" ".join(words))
            parsers = [keyword(w) for w in words]

            parser_sum = parsers[0]
            for i in range(1, len(words)):
                parser_sum = parser_sum + parsers[i]

            try:
                self.statement = (parser_sum >> msg).parse(self.code)
                raise StopIteration()
            except Failure:
                pass

        try:
            for words in Grammar.statements["all"]:
                check(words)
        except StopIteration:
            return

        self.statement = 'assignment'

    def accept(self, visitor):
        return visitor.raw_line(self)

    def __repr__(self):
        return print_details(self)

    def __str__(self):
        return plain(self)


class LogicalLine(object):
    def __init__(self, lines):
        initial_line = [l for l in lines if l.type == 'initial']
        assert len(initial_line) == 1
        initial_line = initial_line[0]

        self.lines = lines
        self.statement = initial_line.statement

        if hasattr(initial_line, 'label'):
            self.label = initial_line.label

        self.code = "\n".join([l.code for l in lines if l.type != 'comment'])

        self.tokens = concat([l.tokens for l in lines if l.type != 'comment'])

    def accept(self, visitor):
        return visitor.logical_line(self)

    def __repr__(self):
        return print_details(self)

    def __str__(self):
        return plain(self)


def parse_into_logical_lines(lines):
    def of_type(type_name):
        return satisfies(lambda l: l.type == type_name, type_name)

    comment, continuation, initial = (of_type(t)
                                      for t in ['comment',
                                                'continuation', 'initial'])

    logical_line = (comment.many() + initial // singleton +
                    (comment | continuation).many()) // LogicalLine

    return logical_line.many().parse(lines)


def parse_source(logical_lines):
    statements = Grammar.statements

    def top_level_block(kind, first_line_optional=False):
        if first_line_optional:
            first_line = one_of_types([kind]).optional()
        else:
            first_line = one_of_types([kind]) // singleton

        mid_lines = (none_of_types(statements["top level"]).many() //
                     inner_block // singleton)
        last_line = one_of_types([["end"] + kind, ["end"]]) // singleton

        block_statement = "_".join(kind + ["block"])

        return ((first_line + mid_lines + last_line) //
                outer_block(block_statement))

    function, subroutine, block_data = [top_level_block(kind)
                                        for kind in [["function"],
                                                     ["subroutine"],
                                                     ["block", "data"]]]

    subprogram = function | subroutine | block_data

    main_program = top_level_block(["program"], True)

    program_unit = subprogram | main_program

    return (+program_unit // outer_block("source_file")).parse(logical_lines)


def one_of_list(names):
    if len(names) == 0:
        return "nothing"
    if len(names) == 1:
        return " ".join(names[0])
    if len(names) == 2:
        return " ".join(names[0]) + " or " + " ".join(names[1])

    proper_names = [" ".join(name) for name in names]
    return "one of " + ", ".join(proper_names) + " or " + " ".join(names[-1])


def one_of_types(names):
    return satisfies(lambda l: l.statement in [" ".join(name)
                                               for name in names],
                     one_of_list(names))


def none_of_types(names):
    return satisfies(lambda l: l.statement not in [" ".join(name)
                                                   for name in names],
                     one_of_list(names))


def remove_blanks(raw_lines):
    empty = satisfies(lambda l: matches(whitespace << EOF, l.original),
                      "empty line")
    remove = (+empty // (lambda ls: RawLine("\n")) | wildcard).many()
    return str((remove // outer_block("source")).parse(raw_lines))


def new_comments(raw_lines):
    def of_type(type_name):
        return satisfies(lambda l: l.type == type_name, type_name)

    def change_comment(line):
        if matches(one_of("c*"), line.original):
            return RawLine("!" + line.original[1:])
        else:
            return line

    upgrade = of_type("comment") // change_comment | wildcard
    return str((upgrade.many() // outer_block("source")).parse(raw_lines))


class Visitor(object):
    def raw_line(self, line):
        return [line.original]

    def logical_line(self, line):
        return concat([l.accept(self) for l in line.lines])

    def inner_block(self, block):
        return concat([b.accept(self) for b in block.blocks])

    def outer_block(self, block):
        return concat([b.accept(self) for b in block.lines])

    def top_level(self, block):
        return block.accept(self)


def indent(doc, indent_width=4):
    margin_column = Grammar.margin_column

    class Indent(object):
        def __init__(self):
            self.current = 1

        def raw_line(self, line):
            if line.type == 'comment':
                return line.original
            code = line.code
            if line.type == 'continuation':
                tab = " " * (self.current + indent_width)
            else:
                tab = " " * self.current

            return line.original[:margin_column] + tab + code.lstrip()

        def logical_line(self, line):
            return "".join([l.accept(self) for l in line.lines])

        def inner_block(self, block):
            self.current += indent_width
            result = "".join([b.accept(self) for b in block.blocks])
            self.current -= indent_width
            return result

        def outer_block(self, block):
            return "".join([b.accept(self) for b in block.content])

    return doc.accept(Indent())


def plain(doc):
    class Plain(object):
        def raw_line(self, line):
            return line.original

        def logical_line(self, line):
            return "".join([b.accept(self) for b in line.lines])

        def outer_block(self, block):
            return "".join([b.accept(self) for b in block.content])

        def inner_block(self, block):
            return "".join([b.accept(self) for b in block.blocks])

    return doc.accept(Plain())


def print_details(doc):
    class Details(object):
        def __init__(self):
            self.level = 0

        def bars(self):
            return "||| " * self.level

        def raw_line(self, line):
            if line.type == "comment":
                result = ""

            elif line.type == "continuation":
                self.level += 1
                result = (self.bars() + self.statement + " continued: " +
                          line.code.lstrip())
                self.level -= 1

            elif line.type == "initial":
                if hasattr(line, 'label'):
                    info = "{}[{}]: ".format(line.statement, line.label)
                else:
                    info = "{}: ".format(line.statement)

                result = self.bars() + info + line.code.lstrip()

            return result

        def logical_line(self, line):
            self.statement = line.statement
            result = "".join([b.accept(self) for b in line.lines])
            del self.statement
            return result

        def outer_block(self, block):
            return "".join([b.accept(self) for b in block.content])

        def inner_block(self, block):
            self.level += 1
            result = "".join([b.accept(self) for b in block.blocks])
            self.level -= 1
            return result

    return doc.accept(Details())


def read_file(filename):
    with open(filename) as fl:
        return [RawLine(line) for line in fl]


def parse_file(filename):
    return parse_source(parse_into_logical_lines(read_file(filename)))


def reconstruct(unit):
    class Reconstruct(object):
        def outer_block(self, block):
            return concat([b.accept(self) for b in block.content])

        def inner_block(self, block):
            return concat([b.accept(self) for b in block.content])

        def logical_line(self, line):
            return concat([l.accept(self) for l in line.lines])

        def raw_line(self, line):
            if line.type == 'comment':
                return [line.original]

            cont_col = Grammar.continuation_column
            marg_col = Grammar.margin_column

            if line.type == 'continuation':
                result = " " * cont_col + line.cont
            else:
                if hasattr(line, 'label'):
                    result = ("{:<" + str(marg_col) + "}").format(line.label)
                else:
                    result = " " * marg_col

            for tok in line.tokens:
                result += tok.value
            return result

    return "".join(unit.accept(Reconstruct()))


def analyze_unit(unit):
    assert isinstance(unit, OuterBlock)

    first = unit.content[0]
    if isinstance(first, LogicalLine):
        tokens = [tok for tok in first.tokens
                  if tok.tag != 'whitespace' and tok.tag != 'comment']

        assert len(tokens) > 0
        assert tokens[0].tag == 'name', "got {}".format(tokens[0].tag)

        program_name = tokens[0].value
        formal_params = [tok.value for tok in tokens[1:] if tok.tag == 'name']

        print first.statement, program_name, formal_params
        print
        main_block = unit.content[1]
        assert len(unit.content) == 3

    else:
        print "unnamed program"
        print
        program_name = None
        formal_params = []
        main_block = unit.content[0]
        assert len(unit.content) == 2

    class Label(object):
        def outer_block(self, block):
            return concat([b.accept(self) for b in block.content])

        def inner_block(self, block):
            return concat([b.accept(self) for b in block.blocks])

        def logical_line(self, line):
            if hasattr(line, 'label'):
                return [line.label]
            else:
                return []

        def raw_line(self, line):
            raise ValueError("raw lines should not be for this visitor")

    labels = list(main_block.accept(Label()))
    print "labels:", labels
    print

    names = [[]]

    class Tokenize(object):
        def outer_block(self, block):
            for b in block.content:
                b.accept(self)

        def inner_block(self, block):
            for b in block.content:
                b.accept(self)

        def logical_line(self, line):
            names[0] += [tok.value for tok in line.tokens if tok.tag == 'name']

        def raw_line(self, line):
            raise ValueError("raw lines should not be for this visitor")

    main_block.accept(Tokenize())

    unique_names = list(set(names[0]))

    print 'names:', unique_names
    print

    print reconstruct(unit)


def _argument_parser_():
    arg_parser = ArgumentParser()
    task_list = ['remove-blanks', 'print-details',
                 'indent', 'new-comments', 'plain', 'analyze']
    arg_parser.add_argument("task", choices=task_list,
                            metavar="task",
                            help="in {}".format(task_list))
    arg_parser.add_argument("filename")
    return arg_parser


def main():
    arg_parser = _argument_parser_()
    args = arg_parser.parse_args()

    raw_lines = read_file(args.filename)
    logical_lines = parse_into_logical_lines(read_file(args.filename))
    parsed = parse_source(logical_lines)

    if args.task == 'plain':
        print plain(parsed)
    elif args.task == 'remove-blanks':
        print remove_blanks(raw_lines)
    elif args.task == 'indent':
        print indent(parsed)
    elif args.task == 'print-details':
        print print_details(parsed)
    elif args.task == 'new-comments':
        print new_comments(raw_lines)
    elif args.task == 'analyze':
        for e in parsed.content:
            analyze_unit(e)
    else:
        raise ValueError("invalid choice: {}".format(args.task))


if __name__ == '__main__':
    main()
