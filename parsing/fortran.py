from argparse import ArgumentParser
import pprint
import sys

from . import alphanumeric, letter, digit, one_of, whitespace, none_of
from . import Failure, succeed, matches, fail
from . import join, exact, token, satisfies, singleton, EOF, parser

control_nonblock_statements = [['go', 'to'], ['call'], ['return'], ['continue'], 
        ['stop'], ['pause']]

control_block_statements = [['if'], ['else', 'if'], ['else'],
               ['end', 'if'], ['do'],
               ['end', 'do']]

control_statements = control_block_statements + control_nonblock_statements

io_statements =  [['read'], ['write'], ['print'], ['rewind'],
               ['backspace'], ['endfile'], ['open'], ['close'], ['inquire']]

assign_statements = [['assign']]

executable_statements = (control_statements + 
        assign_statements + io_statements)

type_statements = [['integer'], ['real'], 
               ['double', 'precision'], ['complex'], ['logical'], ['character']]

specification_statements = type_statements + [['dimension'], ['common'], 
               ['equivalence'], ['implicit'], ['parameter'], ['external'], 
               ['intrinsic'], ['save']]


top_level_statements = [['program'], ['end', 'program'],
               ['function'], ['end', 'function'], ['subroutine'],
               ['end', 'subroutine'], ['block', 'data'],
               ['end', 'block', 'data'], ['end']]

misc_nonexec_statements = [['entry'], ['data'], ['format']]

non_executable_statements = (specification_statements 
        + misc_nonexec_statements + top_level_statements)
                

# order is important here
statements = executable_statements + non_executable_statements

def outer_block(statement):
    def inner(content):
        return OuterBlock(content, statement)
    return inner

class OuterBlock(object):
    def __init__(self, content, statement):
        self.content = content
        self.statement = statement

        assert len(content) == 3
        self.begin, self.inner_block, self.end = content

    def __repr__(self):
        result = ""
        result += repr(self.begin)
        result += ">>"
        result += repr(self.inner_block)
        result += "<<"
        result += repr(self.end)
        return result


    def __str__(self):
        return str(self.begin) + str(self.inner_block) + str(self.end)

def inner_block(content):
    return InnerBlock(content)

class InnerBlock(object):
    def __init__(self, content):
        # this is a list of LogicalLines
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

        if_block = fail("if")

        @parser
        def proper_do_block(text, start):
            #if start >= len(text):
            #    print "proper do block at EOF"
            #else:
            #    print "proper do block at line", start + 1, text[start]
            #sys.stdout.flush()

            success = (((do_statement // singleton)
                + ((non_block | do_block | if_block | none_of_types([["end", "do"]])).many() // inner_block // singleton)
                + (end_do_statement // singleton)) // outer_block("do_block")).scan(text, start)

            #if success.end >= len(text):
            #    print "exiting proper do block at EOF"
            #else:
            #    print "exiting proper do block at line", success.end + 1, text[success.end]
            #sys.stdout.flush()
            return success
 
        @parser
        def do_block(text, start):
            #if start >= len(text):
            #    print "do block at EOF"
            #else:
            #    print "do block at line", start + 1, text[start]
            #sys.stdout.flush()

            success = (proper_do_block | do_statement).scan(text, start)
            #if success.end >= len(text):
            #    print "exisiting do block at EOF"
            #else:
            #    print "exiting  do block at line", success.end + 1, text[success.end]
            #sys.stdout.flush()
            return success
       
        block_or_line = non_block | do_block | if_block | satisfies(lambda l: True, "")

        # this is a list of LogicalLines or OuterBlocks
        for l in content:
            assert isinstance(l, LogicalLine) or isinstance(l, OuterBlock), "got {}".format(type(l))
        self.blocks = block_or_line.many().parse(content)

    def __repr__(self):
        return "\n".join(["   " + str(elem).strip() for elem in self.blocks])

special = one_of(" =+-*/().,$'\":")
name = letter + ~alphanumeric // join
label = digit.between(1, 5) // join

def keyword(string):
    return token(exact(string))


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
                self.statement = (parser >> msg).parse(self.code)
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
        orig = self.original.rstrip()
        if self.type == "comment":
            return "{:23s}: {}".format("comment", orig)

        code = self.code.rstrip()
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
            result += "{} statement with label {}: ".format(self.statement, self.label)
        else:
            result += "{} statement: ".format(self.statement)

        # result += "".join([l.original for l in self.lines]) + "---\n"
        result += self.code.rstrip()

        # return result + "-------"
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

    return (~logical_line).parse(lines)
        

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

    return (+program_unit).parse(logical_lines)


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

# empty = satisfies(lambda l: matches(whitespace << EOF, l.original), "empty line")
# remove_blanks = ~(+empty // (lambda ls: Line("\n")) | satisfies(lambda l: True, ""))

def _argument_parser_():
    parser = ArgumentParser()
    parser.add_argument("filename")
    return parser

def read_file(filename):
    with open(filename) as fl:
        return [Line(line) for line in fl]

def parse_file(filename):
    return parse_source(parse_into_logical_lines(read_file(filename)))

if __name__ == '__main__':
    sys.setrecursionlimit(150)
    args = _argument_parser_().parse_args()

    raw_lines = read_file(args.filename)
    logical_lines = parse_into_logical_lines(read_file(args.filename))

    parsed = parse_source(logical_lines)
    #pprint.pprint(parsed, indent=4)

    for elem in parsed:
        print "======>", elem.statement
        print repr(elem)
