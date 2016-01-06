from argparse import ArgumentParser

from . import alphanumeric, letter, digit, one_of, whitespace, none_of
from . import Failure, succeed, matches
from . import join, exact, token, satisfies, singleton, EOF


control_statements = [['go', 'to'], ['if'], ['else', 'if'], ['else'],
               ['end', 'if'], ['continue'], ['stop'], ['pause'], ['do'],
               ['end', 'do'],
               ['call'], ['return'], ['end']]

io_statements =  [['read'], ['write'], 
        ['print'], ['rewind'],
               ['backspace'], ['endfile'], ['open'], ['close'], ['inquire']]

executable_statements = control_statements + [['assign']] + io_statements


type_statements = [['integer'], ['real'], 
               ['double', 'precision'], ['complex'], ['logical'], ['character']]

specification_statements = type_statements + [['dimension'], ['common'], 
               ['equivalence'], ['implicit'], ['parameter'], ['external'], 
               ['intrinsic'], ['save']]

non_executable_statements = specification_statements + [['program'], ['end', 'program'],
               ['function'], ['end', 'function'], ['subroutine'],
               ['end', 'subroutine'], ['block', 'data'],
               ['end', 'block', 'data'],   
               ['entry'], ['data'], ['format']] 

# order is important here
statements = non_executable_statements + executable_statements

special = one_of(" =+-*/().,$'\":")
name = letter + ~alphanumeric // join
label = digit.between(1, 5) // join

def keyword(string):
    return token(exact(string))

def one_of_list(names):
    if len(names) == 0:
        return "nothing"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return names[0] + " or " + names[1]
    return "one of " + ", ".join(names[:-1]) + " or " + names[-1]

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
            self.label = (token(label) // int).value(statement_label)

        self.code = line[margin:]

        def check(words):
            msg = succeed(" ".join(words))
            parsers = [keyword(w) for w in words]

            parser = parsers[0]
            for i in range(1, len(words)):
                parser = parser + parsers[i]

            try:
                self.statement = (parser >> msg).value(self.code)
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
            result += "{} statement with label {}:\n-\n".format(self.statement, self.label)
        else:
            result += "{} statement:\n-\n".format(self.statement)

        result += "".join([l.original for l in self.lines]) + "---\n"
        result += self.code

        return result + "-------"

    def __str__(self):
        return "".join([str(l) for l in self.lines])


def parse_into_logical_lines(lines):
    def of_type(type_name):
        return satisfies(lambda l: l.type == type_name, type_name)

    comment, continuation, initial = (of_type(t) 
            for t in ['comment', 'continuation', 'initial'])

    logical_line = (~comment + initial // singleton 
                + ~(comment | continuation) 
                + ~comment) // LogicalLine

    return (~logical_line).value(lines)


def parse_source(logical_lines):
    def one_of(names):
        return satisfies(lambda l: l.statement in names, 
                one_of_list(names))

    def none_of(names):
        return satisfies(lambda l: l.statement not in names, 
                one_of_list(names))

    function = ((one_of(["function"]) // singleton 
                + ~(none_of(["end", "end function"]))
                + one_of(["end", "end function"]) // singleton) 
                    // (lambda x: {"function": x}))

    subroutine = ((one_of(["subroutine"]) // singleton
                + ~(none_of(["end", "end subroutine"]))
                + one_of(["end", "end subroutine"]) // singleton)
                    // (lambda x: {"subroutine": x}))

    block_data = ((one_of(["block data"]) // singleton 
                + ~(none_of(["end", "end block data"]))
                + one_of(["end", "end block data"]) // singleton)
                    // (lambda x: {"block data": x}))

    subprogram = function | subroutine | block_data

    main_program = ((-one_of(["program"])
            + ~(none_of(["end", "end program"]))
            + one_of(["end", "end program"]) // singleton)
                    // (lambda x: {"program": x}))

    program_unit = subprogram | main_program

    return (~program_unit).value(logical_lines)

# empty = satisfies(lambda l: matches(whitespace << EOF, l.original), "empty line")
# remove_blanks = ~(+empty // (lambda ls: Line("\n")) | satisfies(lambda l: True, ""))

def _argument_parser_():
    parser = ArgumentParser()
    parser.add_argument("filename")
    return parser

def read_file(filename):
    with open(filename) as fl:
        return [Line(line) for line in fl]

if __name__ == '__main__':
    args = _argument_parser_().parse_args()

    raw_lines = read_file(args.filename)
    logical_lines = parse_into_logical_lines(read_file(args.filename))

    parsed = parse_source(logical_lines)
    for l in parsed:
        for key, value in l.iteritems():
            print ">", key, "<"

            for ll in value:
                print str(ll),
            
        print
        print


    
