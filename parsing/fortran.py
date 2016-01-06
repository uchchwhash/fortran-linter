from argparse import ArgumentParser

from . import alphanumeric, letter, digit, space, whitespace

from . import Failure, succeed

from . import one_of, digits, join, terminal, token

special = one_of(" =+-*/().,$':")
name = letter + ~alphanumeric // join
label = digit.between(1, 5) // join

def key(string):
    return token(terminal(string))

def read_file(filename):
    with open(filename) as fl:
        return [Line(ln + 1, line) for ln, line in enumerate(fl)]

class Line(object):
    def __init__(self, ln, line):
        self.ln = ln
        self.original = line

        lowered = line.rstrip().lower()
        self.lowered = lowered

        cont = 5
        margin = cont + 1
        if len(lowered) == 0 or lowered[0] == '*' or lowered[0] == 'c' or lowered[0] == '!':
            self.type = "comment"
            return

        if len(lowered) > cont and lowered[cont] != " " and lowered[cont] != '0':
            self.type = "continuation"
            assert len(lowered[:cont].strip()) == 0
            self.code = line[margin:]
            return 

        self.type = "initial"

        statement_label = lowered[:cont]
        if len(statement_label.strip()) > 0:
            self.label = (token(label) // int).parse(lowered[:cont]).value

        self.code = line[margin:]

        self.statement = 'none'
        
        def check(words):
            msg = succeed(" ".join(words))
            parsers = map(key, words)

            parser = parsers[0]
            for i in range(1, len(words)):
                parser = parser + parsers[i]

            try:
                self.statement = (parser >> msg).parse(self.code).value
            except Failure:
                pass

            if self.statement != 'none':
                raise StopIteration()

        try:
            check(['assign'])
            check(['go', 'to'])
            check(['if'])
            check(['else', 'if'])
            check(['else'])
            check(['end', 'if'])
            check(['continue'])
            check(['stop'])
            check(['pause'])
            check(['do'])
            check(['end', 'do'])
            check(['read'])
            check(['write'])
            check(['print'])
            check(['rewind'])
            check(['backspace'])
            check(['end', 'file'])
            check(['open'])
            check(['close'])
            check(['inquire'])
            check(['call'])
            check(['return'])
            check(['program'])
            check(['end', 'program'])
            check(['function'])
            check(['end', 'function'])
            check(['subroutine'])
            check(['end', 'subroutine'])
            check(['entry'])
            check(['block', 'data'])
            check(['dimension'])
            check(['common'])
            check(['equivalence'])
            check(['implicit'])
            check(['parameter'])
            check(['external'])
            check(['intrinsic'])
            check(['save'])
            check(['integer'])
            check(['real'])
            check(['double', 'precision'])
            check(['complex'])
            check(['logical'])
            check(['character'])
            check(['data'])
            check(['format'])
            check(['end'])
        except StopIteration:
            return

        try:
            value = key("!").parse(self.code).value
            del self.code
            del self.statement
            self.type = "comment"
            return
        except Failure:
            pass

        self.statement = 'assignment'

    def __repr__(self):
        orig = self.original.rstrip()
        if self.type == "comment":
            return "comment: " + orig

        code = self.code.rstrip()
        if self.type == "continuation":
            return "continuation: " + code

        if hasattr(self, 'label'):
            return self.statement + ": " + str(self.label) + " -> " + code
        return self.statement + ": " + code


def _argument_parser_():
    parser = ArgumentParser()
    parser.add_argument("filename")
    return parser

if __name__ == '__main__':
    args = _argument_parser_().parse_args()

    for l in read_file(args.filename):
        print l
