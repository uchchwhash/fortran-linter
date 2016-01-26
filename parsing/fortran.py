from . import alphanumeric, letter, digit, one_of, whitespace, none_of
from . import Failure, succeed, matches, spaces, wildcard
from . import join, exact, liberal, satisfies, singleton, EOF, parser, concat

from argparse import ArgumentParser
from collections import defaultdict, namedtuple


def inexact(string):
    return exact(string, ignore_case=True)


def keyword(string):
    return liberal(inexact(string))


def sum_parsers(parsers):
    result = succeed("")

    for this in parsers:
        result = result + this

    return result


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


def name_tokens(ls):
    return [token.value.lower() for token in ls if token.tag == 'name']


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

    intrinsics = ['abs', 'acos', 'aimag', 'aint', 'alog',
                  'alog10', 'amax10', 'amax0', 'amax1', 'amin0',
                  'amin1', 'amod', 'anint', 'asin', 'atan',
                  'atan2', 'cabs', 'ccos', 'char', 'clog',
                  'cmplx', 'conjg', 'cos', 'cosh', 'csin',
                  'csqrt', 'dabs', 'dacos', 'dasin', 'datan',
                  'datan2', 'dble', 'dcos', 'dcosh', 'ddim',
                  'dexp', 'dim', 'dint', 'dint', 'dlog', 'dlog10',
                  'dmax1', 'dmin1', 'dmod', 'dnint', 'dprod',
                  'dreal', 'dsign', 'dsin', 'dsinh', 'dsqrt',
                  'dtan', 'dtanh', 'exp', 'float', 'iabs', 'ichar',
                  'idim', 'idint', 'idnint', 'iflx', 'index',
                  'int', 'isign', 'len', 'lge', 'lgt', 'lle',
                  'llt', 'log', 'log10', 'max', 'max0', 'max1',
                  'min', 'min0', 'min1', 'mod', 'nint', 'real',
                  'sign', 'sin', 'sinh', 'sngl', 'sqrt', 'tan', 'tanh',
                  'matmul', 'cycle']

    term = inexact

    name = letter + alphanumeric.many() // join
    label = digit.between(1, 5) // join
    integer = (one_of("+-").optional() + +digit) // join
    logical = term(".true.") | term(".false.")
    char_segment = ((term('"') + none_of('"').many() // join + term('"')) |
                    (term("'") + none_of("'").many() // join + term("'")))

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
    lt, le, eq, ne, gt, ge = [term(c)
                              for c in ['.lt.', '.le.', '.eq.',
                                        '.ne.', '.gt.', '.ge.']]
    not_, and_, or_ = [term(c)
                       for c in ['.not.', '.and.', '.or.']]
    eqv, neqv = [term(c) for c in ['.eqv.', '.neqv.']]
    lparen, rparen, dot, comma, dollar = [exact(c) for c in "().,$"]
    apostrophe, quote, colon, langle, rangle = [exact(c) for c in "'\":<>"]
    exponent = exact("**")
    concatenation = exact("//")

    single_token = (character // tag_token("character") |
                    comment // tag_token("comment") |
                    logical // tag_token("logical") |
                    lt // tag_token("lt") |
                    le // tag_token("le") |
                    eq // tag_token("eq") |
                    ne // tag_token("ne") |
                    gt // tag_token("gt") |
                    ge // tag_token("ge") |
                    not_ // tag_token("not") |
                    and_ // tag_token("and") |
                    or_ // tag_token("or") |
                    eqv // tag_token("eqv") |
                    neqv // tag_token("neqv") |
                    real // tag_token("real") |
                    integer // tag_token("integer") |
                    name // tag_token("name") |
                    equals // tag_token("equals") |
                    plus // tag_token("plus") |
                    minus // tag_token("minus") |
                    exponent // tag_token("exponent") |
                    times // tag_token("times") |
                    concatenation // tag_token("concat") |
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
    def inner(children):
        return OuterBlock(children, statement)
    return inner


class OuterBlock(object):
    def __init__(self, children, statement):
        self.children = children
        self.statement = statement

    def accept(self, visitor):
        return visitor.outer_block(self)

    def __repr__(self):
        return print_details(self)

    def __str__(self):
        return plain(self)


def inner_block(logical_lines):
    return InnerBlock(logical_lines)


class InnerBlock(object):
    def __init__(self, logical_lines):
        statements = Grammar.statements

        @parser
        def if_block(text, start):
            def new_style_if(ll):
                then = [token for token in name_tokens(ll.tokens_after)
                        if token == 'then']
                return len(then) > 0

            if_statement = one_of_types([["if"]])
            else_if_statement = one_of_types([["else", "if"]])
            else_statement = one_of_types([["else"]])
            end_if_statement = one_of_types([["end", "if"]])

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

        @parser
        def do_block(text, start):
            def new_style_do(ll):
                return not matches(keyword("do") + liberal(Grammar.label),
                                   ll.code.lower())

            do_statement = one_of_types([["do"]])
            end_do_statement = one_of_types([["end", "do"]])

            begin = (do_statement.guard(new_style_do, "new style do") //
                     singleton)

            inner = ((non_block | do_block | if_block |
                      none_of_types([["end", "do"]]))
                     .many() // inner_block // singleton)
            end = end_do_statement // singleton

            return (((begin + inner + end) // outer_block("do_block"))
                    .scan(text, start))

        non_block = one_of_types(statements["io"] + statements["assign"] +
                                 statements["specification"] +
                                 statements["misc nonexec"] +
                                 statements["control nonblock"])

        block_or_line = non_block | do_block | if_block | wildcard

        self.children = block_or_line.many().parse(logical_lines)

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

        self.code = line[margin_column:]
        self.tokens = Grammar.tokenizer.parse(self.code)
        self.tokens_after = self.tokens

        if len(lowered) > continuation_column:
            if matches(none_of("0 "), lowered, continuation_column):
                self.type = "continuation"
                assert len(lowered[:continuation_column].strip()) == 0
                self.cont = line[continuation_column:margin_column]
                return

        self.type = "initial"

        statement_label = lowered[:continuation_column]
        if len(statement_label.strip()) > 0:
            self.label = (liberal(Grammar.label) // int).parse(statement_label)

        def check(words):
            msg = succeed(" ".join(words))
            parser_sum = sum_parsers([keyword(w) for w in words])

            try:
                success = (parser_sum >> msg).scan(self.code)
                tokenizer = Grammar.tokenizer

                self.statement = success.value
                self.tokens_after = tokenizer.parse(self.code,
                                                    success.end)
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
    def __init__(self, children):
        initial_line = [l for l in children if l.type == 'initial']
        assert len(initial_line) == 1
        initial_line = initial_line[0]

        self.children = children
        self.statement = initial_line.statement

        try:
            self.label = initial_line.label
        except AttributeError:
            pass

        code_lines = [l for l in children if l.type != 'comment']

        self.code = "\n".join([l.code for l in code_lines])
        self.tokens = concat([l.tokens for l in code_lines])
        self.tokens_after = concat([l.tokens_after for l in code_lines])

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
        return concat([l.accept(self) for l in line.children])

    def inner_block(self, block):
        return concat([b.accept(self) for b in block.children])

    def outer_block(self, block):
        return concat([b.accept(self) for b in block.children])

    def top_level(self, block):
        return "".join(block.accept(self))


def indent(doc, indent_width=4):
    margin_column = Grammar.margin_column

    class Indent(Visitor):
        def __init__(self):
            self.current = 1

        def raw_line(self, line):
            if line.type == 'comment':
                return [line.original]

            if line.type == 'continuation':
                tab = " " * (self.current + indent_width)
            else:
                tab = " " * self.current

            return [line.original[:margin_column] + tab + line.code.lstrip()]

        def inner_block(self, block):
            self.current += indent_width
            result = concat([b.accept(self) for b in block.children])
            self.current -= indent_width
            return result

    return Indent().top_level(doc)


def plain(doc):
    return Visitor().top_level(doc)

def remove_comments(doc):
    class Remove(Visitor):
        def raw_line(self, line):
            if line.type == 'comment':
                return []
            else:
                return [line.original]

    return Remove().top_level(doc)

def print_details(doc):
    class Details(Visitor):
        def __init__(self):
            self.level = 0
            self.statement = None

        def raw_line(self, line):
            if line.type == "comment":
                return []

            elif line.type == "continuation":
                self.level += 1
                result = ["||| " * self.level + self.statement +
                          " continued: " + line.code.lstrip()]
                self.level -= 1
                return result

            elif line.type == "initial":
                try:
                    info = "{}[{}]: ".format(line.statement, line.label)
                except AttributeError:
                    info = "{}: ".format(line.statement)

                return ["||| " * self.level + info + line.code.lstrip()]

        def logical_line(self, line):
            self.statement = line.statement
            return concat([b.accept(self) for b in line.children])

        def inner_block(self, block):
            self.level += 1
            result = concat([b.accept(self) for b in block.children])
            self.level -= 1
            return result

    return Details().top_level(doc)


def read_file(filename):
    with open(filename) as fl:
        return [RawLine(line) for line in fl]


def parse_file(filename):
    return parse_source(parse_into_logical_lines(read_file(filename)))


def reconstruct(unit):
    class Reconstruct(Visitor):
        def raw_line(self, line):
            if line.type == 'comment':
                return [line.original]

            cont_col = Grammar.continuation_column
            marg_col = Grammar.margin_column

            if line.type == 'continuation':
                result = " " * cont_col + line.cont
            else:
                try:
                    result = ("{:<" + str(marg_col) + "}").format(line.label)
                except AttributeError:
                    result = " " * marg_col

            for token in line.tokens:
                result += token.value
            return [result]

    return Reconstruct().top_level(unit)


def collect_unit_names(source):
    unit_names = []

    for unit in source.children:
        assert isinstance(unit, OuterBlock)

        first = unit.children[0]

        if isinstance(first, LogicalLine):
            unit_names.append(mentioned_names(first)[0])

    return unit_names


def analyze(source):
    unit_names = collect_unit_names(source)

    print 'units:', unit_names
    print

    for unit in source.children:
        analyze_unit(unit, unit_names)


def mentioned_names(line):
    return [token for token in name_tokens(line.tokens_after)]


def analyze_header(unit):
    first = unit.children[0]

    if isinstance(first, LogicalLine):
        statement = first.statement

        tokens = [token for token in first.tokens_after
                  if token.tag != 'whitespace' and token.tag != 'comment']

        assert len(tokens) > 0
        assert tokens[0].tag == 'name', "got {}".format(tokens[0].tag)

        program_name = tokens[0].value
        formal_params = name_tokens(tokens[1:])

        assert len(unit.children) == 3
        main_block = unit.children[1]

    else:
        statement = "program"
        program_name = None
        formal_params = []

        assert len(unit.children) == 2
        main_block = unit.children[0]

    return statement, program_name, formal_params, main_block

Interval = namedtuple('Interval', ['var', 'start', 'end'])

def make_timeline(occur_dict):
    occur_list = [Interval(var, occur_dict[var][0], occur_dict[var][-1])
                  for var in occur_dict if occur_dict[var] != []]
    return sorted(occur_list, key=lambda x: x.start)

def draw_timeline(occur_list, last_line, graph_cols=60):
    def graph_pos(lineno):
        return int(round((float(lineno) / last_line) * graph_cols))

    graph_list = [Interval(d.var, graph_pos(d.start), graph_pos(d.end))
                  for d in occur_list]

    for d in graph_list:
        print "{:10s}|{}{}{}|".format(str(d.var),
                                      " " * d.start,
                                      "=" * (d.end - d.start + 1),
                                      " " * (graph_cols - d.end))

    print


def analyze_labels(unit, main_block):
    class Label(Visitor):
        def __init__(self):
            self.current_line = 0

        def logical_line(self, line):
            self.current_line += 1

            try:
                if line.statement != 'format':
                    return [(self.current_line, line.label)]
            except AttributeError:
                pass

            return []

    labels = main_block.accept(Label())
    if labels:
        print "labels:", [lbl for _, lbl in labels]
        print

    occur_dict = defaultdict(list)
    last_line = [0]

    for decl_line, lbl in labels:
        class Occurrences(Visitor):
            def __init__(self):
                self.current_line = 0

            def logical_line(self, line):
                self.current_line += 1
                last_line[0] = self.current_line

                int_tokens = [int(token.value)
                              for token in line.tokens_after
                              if token.tag == 'integer']
                if lbl in int_tokens:
                    occur_dict[lbl].append(self.current_line)

                return []

        main_block.accept(Occurrences())

    for decl_line, lbl in labels:
        print lbl, '@' + str(decl_line), occur_dict[lbl]
        occur_dict[lbl] = sorted(occur_dict[lbl] + [decl_line])
    print

    draw_timeline(make_timeline(occur_dict), last_line[0])


def analyze_variables(unit, unit_names, formal_params, main_block):
    class Variables(Visitor):
        def logical_line(self, line):
            if line.statement == 'format':
                return []
            return mentioned_names(line)

    unique_names = list(set(main_block.accept(Variables())))

    specs = [" ".join(s)
             for s in Grammar.statements["specification"]]

    class Locals(Visitor):
        def logical_line(self, line):
            if line.statement not in specs:
                return []

            name_list = mentioned_names(line)

            if line.statement == 'implicit' and name_list == ['none']:
                return []

            return name_list

    local_variables = list(set(main_block.accept(Locals())))

    keywords = list(set(concat(Grammar.statements["all"]))) + ['then', 'none']

    local_names = list(set(local_variables + formal_params))

    unaccounted_for = list(set(unique_names) - set(local_names) -
                           set(keywords) - set(Grammar.intrinsics) -
                           set(unit_names))
    if unaccounted_for:
        print 'unaccounted_for:', unaccounted_for
        print

    concern = list(set(local_variables + unaccounted_for))

    occur_dict = defaultdict(list)

    last_line = [0]

    for var in concern:
        class Occurrences(Visitor):
            def __init__(self):
                self.current_line = 0

            def logical_line(self, line):
                self.current_line += 1
                last_line[0] = self.current_line
                if line.statement not in specs:
                    if var in name_tokens(line.tokens_after):
                        occur_dict[var].append(self.current_line)

                return []

        main_block.accept(Occurrences())

    never_occur_list = sorted([var for var in concern if occur_dict[var] == []])

    if never_occur_list:
        print 'never occurred:', never_occur_list
        print

    for var in occur_dict:
        print var, occur_dict[var]

    draw_timeline(make_timeline(occur_dict), last_line[0])

    occur_list = [Interval(var, occur_dict[var][0], occur_dict[var][-1])
                  for var in occur_dict if occur_dict[var] != []]
    break_at = 365
    before_list = sorted([d for d in occur_list if d.end < break_at],
            key=lambda x: x.start)
    
    print 'before:'
    draw_timeline(before_list, last_line[0])

    after_list = sorted([d for d in occur_list if d.start > break_at],
            key=lambda x: x.start)

    print 'after:'
    draw_timeline(after_list, last_line[0])

    confused_list = sorted(list(set(occur_list) - set(before_list) 
        - set(after_list)), key=lambda x: x.start)

    print 'confused:'
    draw_timeline(confused_list, last_line[0])

def analyze_unit(unit, unit_names):
    statement, program_name, formal_params, main_block = analyze_header(unit)

    print statement, program_name, formal_params
    print

    analyze_labels(unit, main_block)

    analyze_variables(unit, unit_names, formal_params, main_block)


def _argument_parser_():
    arg_parser = ArgumentParser()
    task_list = ['remove-blanks', 'print-details',
                 'indent', 'new-comments', 'plain', 'analyze',
                 'reconstruct', 'remove-comments']
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
        print plain(parsed),
    elif args.task == 'remove-comments':
        print remove_comments(parsed)
    elif args.task == 'remove-blanks':
        print remove_blanks(raw_lines),
    elif args.task == 'indent':
        print indent(parsed),
    elif args.task == 'print-details':
        print print_details(parsed),
    elif args.task == 'new-comments':
        print new_comments(raw_lines),
    elif args.task == 'reconstruct':
        print reconstruct(parsed),
    elif args.task == 'analyze':
        analyze(parsed)
    else:
        raise ValueError("invalid choice: {}".format(args.task))


if __name__ == '__main__':
    main()
