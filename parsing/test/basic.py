import unittest
from .. import terminal, Failure, EOF, singleton, fail, succeed, join, regex
from .. import space, spaces, letter, word, digit, digits, one_of, none_of

class TestBasic(unittest.TestCase):
    def setUp(self):
        pass

    def match(self, test, text, value, end=None):
        success = test.parse(text)

        self.assertEqual(success.value, value)
        if end is not None:
            self.assertEqual(success.end, end)

    def fail(self, test, text, expected, start=None):
        with self.assertRaises(Failure) as failure:
            test.parse(text)

        self.assertEqual(failure.exception.expected, expected)
        if start is not None:
            self.assertEqual(failure.exception.start, start)

    def test_terminal(self):
        text = "this"

        self.match(terminal("this"), text, text, len(text))
        self.match(terminal("th"), text, "th", len("th"))

        self.fail(terminal("is"), text, repr("is"), 0)


    def test_succeed(self):
        text = "hello world"

        self.match(succeed(True), text, True, 0)

    def test_ignore(self):
        text = "hello world"

        test = terminal("hello") >> terminal(" ") >> terminal("world")
        self.match(test, text, "world", len(text))
        self.match(test >> succeed("!"), text, "!", len(text))
        self.match(test >> EOF, text, None, len(text))

        self.fail(terminal("hello") >> EOF, text, "<EOF>", len("hello"))


    def test_choice(self):
        text = "mocha"

        test = terminal("mocha") ^ terminal("latte")
        self.match(test, text, "mocha", len("mocha"))

        test = terminal("latte") ^ terminal("mocha")
        self.match(test, text, "mocha", len("mocha"))

        test = terminal("hi") ^ terminal("there")
        self.fail(test, text, repr("there"), 0)

    def test_try_choice(self):
        text = "interpol"

        p = terminal("inter") >> terminal("national")
        q = terminal("inter") >> terminal("pol") >> succeed("police")
        test = p | q 
        
        self.match(test, text, "police", len("interpol")) 

    def test_label(self):
        text = "rising sun"

        p = terminal("rising") >> terminal(" ")
        q = (terminal("venus") | terminal("mercury")) % "planet"
        test = p >> q

        self.fail(test, text, "planet", len("rising "))


    def test_map(self):
        text = "hello world"

        p = terminal("hello") // singleton
        q = (terminal(" ") >> terminal("world")) // singleton
        test = p + q 

        self.match(test, text, ["hello", "world"])

    def test_many(self):
        text = "AAAABBBBCCCC"

        test = terminal("A").between(2, 5)
        self.match(test, text, ['A'] * 4, 4)

        test = terminal("A") * 3
        self.match(test, text, ['A'] * 3, 3)

        test = terminal("A") * 5
        self.fail(test, text, repr('A'), 4)

        test = terminal("A") * 3 + -terminal("A") + ~terminal("A") + ~terminal("B")
        self.match(test, text, ['A'] * 4 + ['B'] * 4, 8)

        test = ~terminal("A") + -terminal("D") + +terminal("B")
        self.match(test, text, ['A'] * 4 + ['B'] * 4, 8)

        test = ~terminal("A") + +terminal("D")
        self.fail(test, text, repr('D'), 4)


    def test_chars(self):
        self.match(spaces, "    if    ", ' ' * 4, 4)

        text = 'bighero6'
        test = word + digits
        self.match(test, text, text, len(text))

        text = 'g6'
        test = word + digits
        self.match(test, text, text, len(text))

        text = '71'
        test = digit + digit
        self.match(test, text, text, len(text))

    def test_regex(self):
        text = "email me at someone@example.com"

        test = terminal("email me at") >> spaces >> regex(r"(\w+)@(\w+)\.(\w+)")
        match = test.parse(text)
        self.assertEqual(match.value.groups(0), ("someone", "example", "com"))



if __name__ == '__main__':
    unittest.main()
