from argparse import ArgumentParser

from . import alphanumeric, letter, digit, one_of, whitespace, none_of
from . import Failure, succeed, matches
from . import join, exact, token, satisfies, singleton, EOF

special = one_of(" =+-*/().,$'\":")
name = letter + ~alphanumeric // join
label = digit.between(1, 5) // join


def keyword(string):
    return token(exact(string))

def read_file(filename):
    with open(filename) as fl:
        return [Line(line) for line in fl]

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
            parsers = map(keyword, words)

            parser = parsers[0]
            for i in range(1, len(words)):
                parser = parser + parsers[i]

            try:
                self.statement = (parser >> msg).value(self.code)
                raise StopIteration()
            except Failure:
                pass

        statements = [['assign'], ['go', 'to'], ['if'], ['else', 'if'], ['else'],
                       ['end', 'if'], ['continue'], ['stop'], ['pause'], ['do'],
                       ['end', 'do'], ['read'], ['write'], ['print'], ['rewind'],
                       ['backspace'], ['end', 'file'], ['open'], ['close'], ['inquire'],
                       ['call'], ['return'], ['program'], ['end', 'program'],
                       ['function'], ['end', 'function'], ['subroutine'],
                       ['end', 'subroutine'], ['entry'], ['block', 'data'],
                       ['dimension'], ['common'], ['equivalence'], ['implicit'],
                       ['parameter'], ['external'], ['intrinsic'], ['save'],
                       ['integer'], ['real'], ['double', 'precision'], ['complex'],
                       ['logical'], ['character'], ['data'], ['format'], ['end']]

        try:
            for word in statements:
                check(word)
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
        return "".join(map(str, self.lines))
        

def parse_into_logical_lines(lines):
    comment = satisfies(lambda l: l.type == 'comment', 'comment')
    continuation = satisfies(lambda l: l.type == 'continuation', 'continuation')
    initial = satisfies(lambda l: l.type == 'initial', 'initial')

    logical_line = (~comment + initial // singleton 
                + ~(comment | continuation) 
                + ~comment) // LogicalLine

    return (~logical_line).value(lines)


def _argument_parser_():
    parser = ArgumentParser()
    parser.add_argument("filename")
    return parser

# empty = satisfies(lambda l: matches(whitespace << EOF, l.original), "empty line")
# remove_blanks = ~(+empty // (lambda ls: Line("\n")) | satisfies(lambda l: True, ""))

if __name__ == '__main__':
    args = _argument_parser_().parse_args()

    raw_lines = read_file(args.filename)
# raw_nel = remove_blanks.value(raw_lines)

#    for l in raw_nel:
#        print str(l),

    logical_lines = parse_into_logical_lines(read_file(args.filename))
    print "\n".join([repr(l) for l in logical_lines])
    
