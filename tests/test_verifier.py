import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / 'verifier' / 'main.py'
spec = importlib.util.spec_from_file_location('necromancer_verifier', PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class DiffTests(unittest.TestCase):
    def test_matching_nested_data(self):
        self.assertEqual(mod.differences({'a': [1, 2], 'b': 2}, {'a': [1, 2], 'b': 2}), [])

    def test_regression_is_reported(self):
        diffs = mod.differences({'handling_cents': 0}, {'handling_cents': 50})
        self.assertEqual(diffs, [{'path': '$.handling_cents', 'expected': 0, 'actual': 50}])

    def test_bool_and_integer_do_not_match(self):
        self.assertEqual(len(mod.differences({'value': True}, {'value': 1})), 1)


if __name__ == '__main__':
    unittest.main()
