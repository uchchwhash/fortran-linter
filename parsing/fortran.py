from . import alphanumeric, letter, digit, one_of, whitespace, none_of
from . import Failure, succeed, matches, fail
from . import join, exact, token, satisfies, singleton, EOF, parser, join_list

control_nonblock_statements = [['go', 'to'], ['call'], ['return'], ['continue'], 
        ['stop'], ['pause']]

control_block_statements = [['if'], ['else', 'if'], ['else'], ['end', 'if'], 
        ['do'], ['end', 'do']]

control_statements = control_block_statements + control_nonblock_statements

io_statements = [['read'], ['write'], ['print'], ['rewind'], ['backspace'], 
        ['endfile'], ['open'], ['close'], ['inquire']]

assign_statements = [['assign']]

executable_statements = control_statements + assign_statements + io_statements

type_statements = [['integer'], ['real'], ['double', 'precision'], ['complex'], 
        ['logical'], ['character']]

specification_statements = type_statements + [['dimension'], ['common'], 
        ['equivalence'], ['implicit'], ['parameter'], ['external'], ['intrinsic'], 
        ['save']]

top_level_statements = [['program'], ['end', 'program'], ['function'], 
        ['end', 'function'], ['subroutine'], ['end', 'subroutine'], 
        ['block', 'data'], ['end', 'block', 'data'], ['end']]

misc_nonexec_statements = [['entry'], ['data'], ['format']]

non_executable_statements = (specification_statements 
        + misc_nonexec_statements + top_level_statements)
                
# order is important here, because 'end' should come before 'end if' et cetera
statements = executable_statements + non_executable_statements

def outer_block(statement):
    def inner(content):
        return OuterBlock(content, statement)
    return inner

class OuterBlock(object):
    def __init__(self, content, statement):
        self.content = content
        self.statement = statement

    def __repr__(self):
        result = ""

        for elem in self.content:
            if isinstance(elem, InnerBlock):
                lines = repr(elem).split("\n")
                result += "\n".join(["||| " + line for line in lines if line != '']) + "\n"
            else:
                result += repr(elem)

        return result

    def __str__(self):
        return "".join([str(elem) for elem in self.content])


def inner_block(content):
    return InnerBlock(content)

class InnerBlock(object):
    def __init__(self, content):
        # this is a list of `LogicalLine`s
        self.content = content

        non_block_statements = (io_statements + assign_statements
                + specification_statements + misc_nonexec_statements
                + control_nonblock_statements)

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

        def old_style_if(ll):
            return not new_style_if(ll)

        @parser
        def if_block(text, start):
            begin = (if_statement.guard(new_style_if, "new style if") // singleton)
            inner = (non_block | do_block | if_block | 
                none_of_types([["end", "if"], ["else", "if"], ["else"]]))
            else_or_else_if = else_if_statement | else_statement

            def inner_block_or_empty(ls):
                if ls != []:
                    return [inner_block(ls)]
                else:
                    return []

            section = ((inner.many() // inner_block_or_empty) 
                    + else_or_else_if.optional()).guard(lambda l: l != [], "anything")
            sections = section.many() // join_list

            end = (end_if_statement // singleton)

            result = ((begin + sections + end) // outer_block("if_block")).scan(text, start)

            return result

        def new_style_do(ll):
            return not matches(keyword("do") + token(label), ll.code.lower())

        def old_style_do(ll):
            return not new_style_do(ll)

        @parser
        def do_block(text, start):
            begin = do_statement.guard(new_style_do, "new style do") // singleton

            inner = ((non_block | do_block | if_block | none_of_types([["end", "do"]]))
                           .many() // inner_block // singleton)
            end = end_do_statement // singleton

            return ((begin + inner + end) // outer_block("do_block")).scan(text, start)

        block_or_line = non_block | do_block | if_block | satisfies(lambda l: True, "")

        # this is a list of LogicalLines or OuterBlocks
        self.blocks = block_or_line.many().parse(content)

    def __repr__(self):
        return "".join([repr(elem) for elem in self.blocks])

    def __str__(self):
        return "".join([str(elem) for elem in self.content])


class Line(object):
    def __init__(self, line):
        self.original = line

        lowered = line.rstrip().lower()

        cont = 5
        margin = cont + 1

        if matches(EOF | one_of("*c") | keyword("!"), lowered):
            self.type = "comment"
            return

        if len(lowered) > cont and matches(none_of("0 "), lowered, cont):
            self.type = "continuation"
            assert len(lowered[:cont].strip()) == 0
            self.code = line[margin:]
            self.cont = line[cont:margin]
            return 

        self.type = "initial"

        statement_label = lowered[:cont]
        if len(statement_label.strip()) > 0:
            self.label = (token(label) // int).parse(statement_label)

        self.code = line[margin:]

        def check(words):
            msg = succeed(" ".join(words))
            parsers = [keyword(w) for w in words]

            parser = parsers[0]
            for i in range(1, len(words)):
                parser = parser + parsers[i]

            try:
                self.statement = (parser >> msg).parse(self.code.lower())
                raise StopIteration()
            except Failure:
                pass

        try:
            for words in statements:
                check(words)
        except StopIteration:
            return

        self.statement = 'assignment'

    def __repr__(self):
        orig = self.original.lstrip()
        if self.type == "comment":
            return "{:23s}: {}".format("comment", orig)

        code = self.code.lstrip()
        if self.type == "continuation":
            return "{:23s}: {}".format("continuation", code)

        if hasattr(self, 'label'):
            return "{:15s}[{:>5d}] : {}".format(self.statement, self.label, code)
        return "{:23s}: {}".format(self.statement, code)

    def __str__(self):
        return self.original


class LogicalLine(object):
    def __init__(self, lines):
        initial_line = [l for l in lines if l.type == 'initial']
        assert len(initial_line) == 1
        initial_line = initial_line[0]
        
        self.lines = lines
        self.statement = initial_line.statement

        if hasattr(initial_line, 'label'):
            self.label = initial_line.label

        self.code = "".join([l.code for l in lines if l.type != 'comment'])

    def __repr__(self):
        result = ''

        if hasattr(self, 'label'):
            result += "{}[{}]: ".format(self.statement, self.label)
        else:
            result += "{}: ".format(self.statement)

        result += self.code.lstrip()

        return result

    def __str__(self):
        return "".join([str(l) for l in self.lines])


def parse_into_logical_lines(lines):
    def of_type(type_name):
        return satisfies(lambda l: l.type == type_name, type_name)

    comment, continuation, initial = (of_type(t) 
            for t in ['comment', 'continuation', 'initial'])

    logical_line = (comment.many() + initial // singleton 
                + (comment | continuation).many()) // LogicalLine

    return logical_line.many().parse(lines)
        

def parse_source(logical_lines):
    function = ((one_of_types([["function"]]) // singleton
                + none_of_types(top_level_statements).many() // inner_block // singleton
                + one_of_types([["end"], ["end", "function"]]) // singleton)
                    // outer_block("function_block"))

    subroutine = ((one_of_types([["subroutine"]]) // singleton
                + none_of_types(top_level_statements).many() // inner_block // singleton
                + one_of_types([["end"], ["end", "subroutine"]]) // singleton)
                    // outer_block("subroutine_block"))

    block_data = ((one_of_types([["block", "data"]]) // singleton
                + none_of_types(top_level_statements).many() // inner_block // singleton
                + one_of_types([["end"], ["end", "block", "data"]]) // singleton)
                    // outer_block("block_data_block"))

    subprogram = function | subroutine | block_data

    main_program = ((one_of_types([["program"]]).optional() 
                + none_of_types(top_level_statements).many() // inner_block // singleton
                + one_of_types([["end"], ["end", "program"]]) // singleton)
                    // outer_block("program_block"))

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
    return satisfies(lambda l: l.statement in [" ".join(name) for name in names], 
                one_of_list(names))

def none_of_types(names):
    return satisfies(lambda l: l.statement not in [" ".join(name) for name in names], 
                one_of_list(names))

def remove_blanks(raw_lines):
    empty = satisfies(lambda l: matches(whitespace << EOF, l.original), "empty line")
    remove = (+empty // (lambda ls: Line("\n")) | satisfies(lambda l: True, "")).many()
    return str((remove // outer_block("source")).parse(raw_lines))


def indent(doc, indent_width=3):
    def indent_outer(outer, spaces):
        result = ""
        for elem in outer.content:
            if isinstance(elem, InnerBlock):
                result += indent_inner(elem, spaces + (" " * indent_width))
            elif isinstance(elem, LogicalLine):
                result += indent_logical(elem, spaces)
            elif isinstance(elem, OuterBlock):
                result += indent_outer(elem, spaces)
            else:
                raise ValueError("unknown type: {}".format(type(elem)))
        return result

    def indent_inner(inner, spaces):
        result = ""
        for elem in inner.blocks:
            if isinstance(elem, InnerBlock):
                raise ValueError("inner blocks should not be nested: {}"
                        .format(str(inner)))
            elif isinstance(elem, OuterBlock):
                result += indent_outer(elem, spaces)
            elif isinstance(elem, LogicalLine):
                result += indent_logical(elem, spaces)
            else:
                raise ValueError("unknown type: {}".format(type(elem)))
        return result

    def indent_logical(elem, spaces):
        cont = 5
        margin = cont + 1
        result = ""
        for line in elem.lines:
            if line.type == "comment":
                result += line.original
            elif line.type == "continuation":
                result += (" " * cont) + line.cont + spaces + line.code.lstrip()
            elif line.type == "initial":
                after_label = " " + spaces + line.code.lstrip() 
                if hasattr(line, 'label'):
                    result += "{:5s}".format(str(line.label)) + after_label
                else:
                    result += "{:5s}".format("") + after_label
            else:
                raise ValueError("unknown type: {}".format(line.type))
        return result


    return indent_outer(doc, " ")


special = one_of(" =+-*/().,$'\":")
name = letter + ~alphanumeric // join
label = digit.between(1, 5) // join

def keyword(string):
    return token(exact(string))


from argparse import ArgumentParser
from argcomplete import autocomplete, warn
def _argument_parser_():
    parser = ArgumentParser()
    task_list = ['remove-blanks', 'print-details', 'indent', 'new-comments']
    parser.add_argument("task", choices=task_list,
            metavar="task",
            help="in {}".format(task_list))
    parser.add_argument("filename")
    return parser

def read_file(filename):
    with open(filename) as fl:
        return [Line(line) for line in fl]

def parse_file(filename):
    return parse_source(parse_into_logical_lines(read_file(filename)))

if __name__ == '__main__':
    arg_parser = _argument_parser_()
    autocomplete(arg_parser)
    args = arg_parser.parse_args()

    raw_lines = read_file(args.filename)
    logical_lines = parse_into_logical_lines(read_file(args.filename))
    parsed = parse_source(logical_lines)

    if args.task == 'remove-blanks':
        print remove_blanks(raw_lines)
    elif args.task == 'indent':
        print indent(parsed)
    elif args.task == 'print-details':
        print repr(parsed)
    elif args.task == 'new-comments':
        # TODO
        pass
    else:
        raise ValueError("invalid choice: {}".format(args.task))

