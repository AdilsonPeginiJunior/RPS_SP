import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import main


class ResolveInputPathTests(unittest.TestCase):
    def test_returns_provided_path(self):
        self.assertEqual(main.resolve_input_path(
            "C:/tmp/exemplo.xlsx"), "C:/tmp/exemplo.xlsx")

    def test_uses_dialog_when_path_is_missing(self):
        with patch.object(
            main,
            "prompt_for_municipal_registration",
            return_value=("C:/tmp/selecionado.xlsx", "12345678"),
        ):
            self.assertEqual(main.resolve_input_path(
                None), "C:/tmp/selecionado.xlsx")

    def test_format_string_replaces_newlines_with_spaces(self):
        self.assertEqual(main.format_string(
            "Linha 1\nLinha 2", 20), "Linha 1 Linha 2".ljust(20))


class DocumentValidationTests(unittest.TestCase):
    def test_accepts_valid_formatted_cpf(self):
        self.assertEqual(main.validate_document("529.982.247-25"), "52998224725")

    def test_accepts_valid_formatted_cnpj(self):
        self.assertEqual(main.validate_document("11.222.333/0001-81"), "11222333000181")

    def test_rejects_invalid_check_digits(self):
        with self.assertRaises(ValueError):
            main.validate_document("123.456.789-01")

    def test_detail_error_identifies_document_and_responsible(self):
        row = main.pd.Series({
            "RPS Type": "RPS",
            "RPS Series": "E",
            "RPS Number": "7",
            "Issue Date": "2026-09-17",
            "Status": "T",
            "Service Value": "10,00",
            "Service Code": "5118",
            "ISS Rate": "0",
            "Client CPF/CNPJ": "",
            "Client Name": "Maria Responsável",
            "Client Address": "Rua A",
            "Client Number": "1",
            "Client Neighborhood": "Centro",
            "Client City": "São Paulo",
            "Client State": "SP",
            "Client ZIP": "01001000",
            "Client Email": "maria@example.com",
            "Service Description": "Serviço",
        })

        with self.assertRaisesRegex(ValueError, "vazio.*Maria Responsável.*RPS: 7"):
            main.build_detail(row)


class MunicipalRegistrationTests(unittest.TestCase):
    def test_normalizes_formatted_registration_to_eight_digits(self):
        self.assertEqual(
            main.normalize_municipal_registration("1.234.567-8"),
            "12345678",
        )

    def test_rejects_registration_with_wrong_length(self):
        with self.assertRaises(ValueError):
            main.normalize_municipal_registration("1234567")

    def test_header_uses_normalized_registration(self):
        header = main.build_header("1.234.567-8", "20260917", "20260917")
        self.assertEqual(header[:12], "100112345678")


class RpsSequenceTests(unittest.TestCase):
    def test_assigns_numbers_after_last_saved_number(self):
        frame = main.pd.DataFrame({"RPS Number": ["1", "2"]})
        with patch.object(main, "load_last_rps_number", return_value=144):
            numbered = main.assign_next_rps_numbers(frame)

        self.assertEqual(numbered["RPS Number"].tolist(), ["145", "146"])
        self.assertEqual(frame["RPS Number"].tolist(), ["1", "2"])

    def test_assigns_numbers_from_user_defined_first_number(self):
        frame = main.pd.DataFrame({"RPS Number": ["1", "2"]})

        numbered = main.assign_rps_numbers(frame, 300)

        self.assertEqual(numbered["RPS Number"].tolist(), ["300", "301"])

    def test_rejects_zero_as_first_rps_number(self):
        frame = main.pd.DataFrame({"RPS Number": ["1"]})

        with self.assertRaises(ValueError):
            main.assign_rps_numbers(frame, 0)

    def test_settings_preserve_registration_and_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "settings.json"
            with patch.object(main, "SETTINGS_PATH", settings_path):
                main.save_municipal_registration("1.234.567-8")
                main.save_last_rps_number(146)

                self.assertEqual(main.load_municipal_registration(), "12345678")
                self.assertEqual(main.load_last_rps_number(), 146)


class NormalizeColumnsTests(unittest.TestCase):
    def test_accepts_spaces_and_accents_in_portuguese_headers(self):
        columns = {
            " Número RPS ": ["1"],
            "Série RPS": ["E"],
            "Tipo RPS": ["RPS"],
            "Data de Emissão": ["2026-01-01"],
            "Status RPS": ["T"],
            "Valor dos Serviços": ["10.00"],
            "Código do Serviço": ["5118"],
            "Alíquota ISS": ["0"],
            "CPF/CNPJ do Tomador": ["52998224725"],
            "Nome/Razão Social do Tomador": ["Cliente"],
        }
        normalized = main.normalize_columns(main.pd.DataFrame(columns))

        self.assertEqual(normalized["RPS Number"].iloc[0], "1")
        self.assertEqual(normalized["Client Name"].iloc[0], "Cliente")


class ReceiptImportTests(unittest.TestCase):
    def test_extract_receipts_keeps_same_responsible_on_different_dates(self):
        text = (
            "Nome Responsável: Fulano de Tal\n"
            "CPF Responsável: 999.888.777-66\n"
            "Valor do recibo: 300,00\n"
            "Data do recebimento: 02/09/2026\n"
            "Descrição do serviço prestado: Sessão de 02/09/2026\n\n"
            "Nome Responsável: Fulano de Tal\n"
            "CPF Responsável: 999.888.777-66\n"
            "Valor do recibo: 300,00\n"
            "Data do recebimento: 09/09/2026\n"
            "Descrição do serviço prestado: Sessão de 09/09/2026\n\n"
            "Nome Responsável: Fulano de Tal\n"
            "CPF Responsável: 999.888.777-66\n"
            "Valor do recibo: 300,00\n"
            "Data do recebimento: 16/09/2026\n"
            "Descrição do serviço prestado: Sessão de 16/09/2026\n"
        )

        df = main.extract_receipts(text)

        self.assertEqual(len(df), 3)
        self.assertEqual(
            df["Issue Date"].tolist(),
            ["02/09/2026", "09/09/2026", "16/09/2026"],
        )

    def test_extract_receipts_uses_history_for_responsible_who_is_patient(self):
        fake_database = [{
            "Client CPF/CNPJ": "999.888.777-66",
            "Client Name": "Fulano de Tal",
            "Nome do Paciente": "Fulano de Tal",
            "CPF do Paciente": "999.888.777-66",
            "sexo do paciente": "Fem",
        }]
        text = (
            "Nome Responsável: Fulano de Tal\n"
            "CPF Responsável: 999.888.777-66\n"
            "Valor do recibo: 300,00\n"
            "Data do recebimento: 02/09/2026\n"
            "Descrição do serviço prestado: serviço de psicoterapia individual no dia 02/09/2026\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            database_path = Path(tmp_dir) / "clientes.json"
            database_path.write_text(
                main.json.dumps(fake_database, ensure_ascii=False), encoding="utf-8"
            )
            with patch.object(main, "PATIENT_DATABASE_PATH", database_path):
                df = main.extract_receipts(text)

        self.assertIn("Prestação de serviços de psicoterapia", df.loc[0, "Service Description"])
        self.assertIn("Fulano de Tal", df.loc[0, "Service Description"])
        self.assertIn("02/09/2026", df.loc[0, "Service Description"])
        self.assertIn("Sessões realizadas em: 02/09/2026", df.loc[0, "Service Description"])
        self.assertIn("CPF Paciente: 999.888.777-66", df.loc[0, "Service Description"])

    def test_extract_receipts_returns_rps_columns(self):
        text = (
            "Nome paciente: Ana\n"
            "CPF do paciente: 123.456.789-01\n"
            "Valor do recibo: 1.234,56\n"
            "Data do recebimento: 05/08/2026\n"
            "Descrição do serviço prestado: Psicoterapia\n"
        )

        df = main.extract_receipts(text)

        self.assertEqual(list(df.columns), main.EXPECTED_COLUMNS)
        self.assertEqual(df.loc[0, "Service Value"], main.Decimal("1234.56"))
        self.assertEqual(df.loc[0, "Client CPF/CNPJ"], "")

    def test_extract_receipts_uses_responsible_address_from_database(self):
        fake_database = [{
            "Client CPF/CNPJ": "111.222.333-44",
            "Client Name": "Beltrana de Tal",
            "Nome do Paciente": "Fulano de Tal Junior",
            "CPF do Paciente": "555.666.777-88",
            "Client Address": "Rua Exemplo",
            "Client Number": "100",
            "Client Neighborhood": "Bairro Teste",
            "Client City": "Cidade Teste",
            "Client State": "SP",
            "Client ZIP": "00000-000",
            "Client Email": "teste@example.com",
            "sexo do paciente": "Masc",
        }]
        with tempfile.TemporaryDirectory() as tmp_dir:
            database_path = Path(tmp_dir) / "clientes.json"
            database_path.write_text(
                main.json.dumps(fake_database, ensure_ascii=False), encoding="utf-8"
            )
            text = (
                "Nome paciente: Fulano de Tal Junior\n"
                "Nome responsável: Beltrana de Tal\n"
                "CPF responsável: 111.222.333-44\n"
                "CPF paciente: 555.666.777-88\n"
                "Valor do recibo: 900,00\n"
                "Data do recebimento: 31/08/2026\n"
                "Endereço: -\n"
                "Descrição do serviço prestado: Psicoterapia\n"
            )
            with patch.object(main, "PATIENT_DATABASE_PATH", database_path):
                df = main.extract_receipts(text)

        self.assertEqual(df.loc[0, "Client Address"], "Rua Exemplo")
        self.assertEqual(df.loc[0, "Client Number"], "100")
        self.assertEqual(df.loc[0, "Client Neighborhood"], "Bairro Teste")
        self.assertEqual(df.loc[0, "Client City"], "Cidade Teste")
        self.assertEqual(df.loc[0, "Client State"], "SP")
        self.assertEqual(df.loc[0, "Client ZIP"], "00000-000")


class XlsxWarningTests(unittest.TestCase):
    def test_warns_before_sending_when_rps_type_is_not_numeric(self):
        df = main.pd.DataFrame({
            "RPS Number": ["1"],
            "RPS Series": ["E"],
            "RPS Type": ["INVALIDO"],
            "Issue Date": ["2026-01-01"],
            "Status": ["T"],
            "Service Value": ["10.00"],
            "Service Code": ["5118"],
            "ISS Rate": ["0"],
            "Client CPF/CNPJ": ["52998224725"],
            "Client Municipal Registration": [""],
            "Client Name": ["Cliente Exemplo"],
            "Client Address": ["Rua A"],
            "Client Number": ["10"],
            "Client Neighborhood": ["Centro"],
            "Client City": ["São Paulo"],
            "Client State": ["SP"],
            "Client ZIP": ["01001000"],
            "Client Email": ["cliente@exemplo.com"],
            "Service Description": ["Serviço"],
        })

        with patch("main.warnings.warn") as warn:
            main.warn_about_xlsx_corrections(df)

        warn.assert_called_once()
        self.assertIn("corrigir", str(warn.call_args[0][0]).lower())


class OutputAndOpenTests(unittest.TestCase):
    def test_output_txt_stays_in_same_folder_as_xlsx(self):
        output = main.get_output_path_for_xlsx("C:/dados/arquivo.xlsx")
        self.assertEqual(output, Path("C:/dados/arquivo.txt"))

    def test_generate_txt_uses_same_folder_as_xlsx(self):
        frame = main.pd.DataFrame({
            "RPS Number": ["1"],
            "RPS Series": ["E"],
            "RPS Type": ["1"],
            "Issue Date": ["2026-09-17"],
            "Status": ["T"],
            "Service Value": ["10.00"],
            "Service Code": ["5118"],
            "ISS Rate": ["0"],
            "Client CPF/CNPJ": ["52998224725"],
            "Client Municipal Registration": [""],
            "Client Name": ["Cliente"],
            "Client Address": ["Rua A"],
            "Client Number": ["10"],
            "Client Neighborhood": ["Centro"],
            "Client City": ["São Paulo"],
            "Client State": ["SP"],
            "Client ZIP": ["01001000"],
            "Client Email": ["cliente@teste.com"],
            "Service Description": ["Serviço"],
        })

        with patch("main.read_excel", return_value=frame), patch("main.warn_about_xlsx_corrections"), patch("main.create_txt") as create_txt:
            output = main.generate_txt_from_xlsx("C:/dados/arquivo.xlsx", "12345678", open_after_save=False)

        self.assertEqual(output, Path("C:/dados/arquivo.txt"))
        create_txt.assert_called_once_with("C:/dados/arquivo.txt", frame, "12345678")

    def test_open_file_uses_windows_notepad_when_available(self):
        file_path = Path("C:/dados/arquivo.txt")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("teste", encoding="utf-8")

        with patch("main.os.name", "nt"), patch("main.os.startfile", side_effect=OSError), patch("main.subprocess.Popen") as popen:
            main.open_file_in_default_app(file_path)

        popen.assert_called_once_with(["notepad.exe", str(file_path)], shell=False)


if __name__ == "__main__":
    unittest.main()
