import unittest
from unittest.mock import patch

import main


class ResolveInputPathTests(unittest.TestCase):
    def test_returns_provided_path(self):
        self.assertEqual(main.resolve_input_path(
            "C:/tmp/exemplo.xlsx"), "C:/tmp/exemplo.xlsx")

    def test_uses_dialog_when_path_is_missing(self):
        with patch.object(main, "prompt_for_xlsx_file", return_value="C:/tmp/selecionado.xlsx"):
            self.assertEqual(main.resolve_input_path(
                None), "C:/tmp/selecionado.xlsx")

    def test_format_string_replaces_newlines_with_spaces(self):
        self.assertEqual(main.format_string(
            "Linha 1\nLinha 2", 20), "Linha 1 Linha 2".ljust(20))


if __name__ == "__main__":
    unittest.main()
