import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
import warnings
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception:  # pragma: no cover - ambiente sem interface gráfica
    tk = None
    filedialog = None
    messagebox = None

EXPECTED_COLUMNS = [
    "RPS Number",
    "RPS Series",
    "RPS Type",
    "Issue Date",
    "Status",
    "Service Value",
    "Service Code",
    "ISS Rate",
    "Client CPF/CNPJ",
    "Client Municipal Registration",
    "Client Name",
    "Client Address",
    "Client Number",
    "Client Neighborhood",
    "Client City",
    "Client State",
    "Client ZIP",
    "Client Email",
    "Service Description",
]

PROJECT_DIR = Path(__file__).resolve().parent
PATIENT_DATABASE_PATH = PROJECT_DIR / "clientes.json"
RECEIPTS_DATABASE_PATH = PROJECT_DIR / "recibos.json"
SETTINGS_PATH = PROJECT_DIR / ".rps_sp_settings.json"
DEFAULT_LAST_RPS_NUMBER = 144
PATIENT_HISTORY_TEMPLATES = {
    "Fem": PROJECT_DIR / "HistoricoPacienteFem.txt",
    "Masc": PROJECT_DIR / "HistoricoPacienteMasc.txt",
}


def load_settings() -> dict[str, object]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        return settings if isinstance(settings, dict) else {}
    except Exception:
        return {}


def save_settings(settings: dict[str, object]) -> None:
    with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, ensure_ascii=False, indent=2)


def load_open_after_save_preference() -> bool:
    return bool(load_settings().get("open_after_save", True))


def save_open_after_save_preference(value: bool) -> None:
    settings = load_settings()
    settings["open_after_save"] = bool(value)
    save_settings(settings)


def load_last_rps_number() -> int:
    value = load_settings().get("last_rps_number", DEFAULT_LAST_RPS_NUMBER)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LAST_RPS_NUMBER
    return number if number >= 0 else DEFAULT_LAST_RPS_NUMBER


def save_last_rps_number(number: int) -> None:
    settings = load_settings()
    settings["last_rps_number"] = int(number)
    save_settings(settings)


def load_municipal_registration() -> str:
    value = load_settings().get("municipal_registration", "")
    return str(value or "")


def save_municipal_registration(value: str) -> str:
    registration = normalize_municipal_registration(value)
    settings = load_settings()
    settings["municipal_registration"] = registration
    save_settings(settings)
    return registration


def assign_next_rps_numbers(df: pd.DataFrame) -> pd.DataFrame:
    return assign_rps_numbers(df, load_last_rps_number() + 1)


def assign_rps_numbers(df: pd.DataFrame, first_number: int) -> pd.DataFrame:
    if first_number < 1:
        raise ValueError("O primeiro número do RPS deve ser maior que zero.")
    numbered_df = df.copy()
    numbered_df["RPS Number"] = [
        str(first_number + index) for index in range(len(numbered_df))
    ]
    return numbered_df


def remember_highest_rps_number(df: pd.DataFrame) -> None:
    numbers = []
    for value in df.get("RPS Number", []):
        digits = clean_digits(value)
        if digits:
            numbers.append(int(digits))
    if numbers:
        save_last_rps_number(max(load_last_rps_number(), max(numbers)))


def clean_digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value or "")).strip()


def _has_valid_check_digits(digits: str, weights: list[int]) -> bool:
    total = sum(int(digit) * weight for digit, weight in zip(digits, weights))
    remainder = total % 11
    check_digit = 0 if remainder < 2 else 11 - remainder
    return check_digit == int(digits[len(weights)])


def is_valid_cpf(digits: str) -> bool:
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    return _has_valid_check_digits(digits, list(range(10, 1, -1))) and _has_valid_check_digits(
        digits, list(range(11, 1, -1))
    )


def is_valid_cnpj(digits: str) -> bool:
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return _has_valid_check_digits(digits, first_weights) and _has_valid_check_digits(
        digits, second_weights
    )


def validate_document(value: str) -> str:
    digits = clean_digits(value)
    if is_valid_cpf(digits) or is_valid_cnpj(digits):
        return digits
    raise ValueError(
        f"Documento inválido '{value}': informe um CPF ou CNPJ válido, com dígitos verificadores corretos."
    )


def parse_date(value: str) -> str:
    if pd.isna(value) or str(value).strip() == "":
        raise ValueError("Data de emissão ausente.")
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")

    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            continue

    raise ValueError(
        f"Formato de data inválido '{value}'. Use AAAA-MM-DD ou DD/MM/AAAA."
    )


def normalize_text(value: str) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_string(value: str, length: int) -> str:
    normalized = normalize_text(value)
    if len(normalized) > length:
        return normalized[:length]
    return normalized.ljust(length)


def format_description(value: str) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "|")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def format_numeric(value: str, length: int) -> str:
    digits = clean_digits(value)
    if digits == "":
        digits = "0"
    if len(digits) > length:
        raise ValueError(f"Valor numérico '{value}' excede {length} dígitos.")
    return digits.zfill(length)


def normalize_municipal_registration(value: str) -> str:
    text = str(value or "").strip()
    digits = re.sub(r"[.\-/\s]", "", text)
    if not digits.isdigit() or len(digits) != 8:
        raise ValueError(
            f"Inscrição municipal inválida '{value}': informe exatamente 8 dígitos."
        )
    return digits


def format_decimal_to_cents(value: str, length: int) -> str:
    text = str(value or "").strip().replace(" ", "")
    if text == "":
        text = "0"
    text = text.replace(",", ".")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"Valor decimal inválido '{value}'.")

    amount = amount.quantize(Decimal("0.01"))
    cents = int(amount * 100)
    result = str(cents)
    if len(result) > length:
        raise ValueError(
            f"Valor '{value}' em centavos excede {length} dígitos.")
    return result.zfill(length)


def zero_field(length: int) -> str:
    return "0" * length


def space_field(length: int) -> str:
    return " " * length


def build_header(
    municipal_registration: str,
    start_date: str,
    end_date: str,
) -> str:
    return (
        "1"
        + "001"
        + normalize_municipal_registration(municipal_registration)
        + start_date
        + end_date
    )


def build_detail(row: pd.Series) -> str:
    rps_type = format_string(row["RPS Type"], 5)
    rps_series = format_string(row["RPS Series"], 5)
    rps_number = format_numeric(row["RPS Number"], 12)
    issue_date = parse_date(row["Issue Date"])
    status = format_string(row["Status"], 1)
    service_value = format_decimal_to_cents(row["Service Value"], 15)
    deduction_value = format_decimal_to_cents(
        row.get("Service Deductions", "0"), 15)
    service_code = format_numeric(row["Service Code"], 5)
    iss_rate = format_numeric(row["ISS Rate"], 4)

    iss_retained_value = str(row.get("ISS Retained", "")).strip().upper()
    if iss_retained_value in {"1", "S", "SIM", "Y", "YES"}:
        iss_retained = "1"
    elif iss_retained_value in {"3"}:
        iss_retained = "3"
    else:
        iss_retained = "2"

    document_value = row.get("Client CPF/CNPJ", "")
    try:
        tomador_document = validate_document(document_value)
    except ValueError as error:
        found_value = normalize_text(document_value) or "(vazio)"
        responsible_name = normalize_text(row.get("Client Name", "")) or "(não informado)"
        rps_number = normalize_text(row.get("RPS Number", "")) or "(não informado)"
        raise ValueError(
            f"{error} Valor encontrado: '{found_value}'. "
            f"Responsável: '{responsible_name}'. RPS: {rps_number}."
        ) from error
    cpf_cnpj_indicator = "2" if len(tomador_document) == 14 else "1"
    municipal_reg = format_numeric(
        row.get("Client Municipal Registration", ""), 8)
    state_registration = format_numeric(
        row.get("Client State Registration", ""), 12)
    name = format_string(row["Client Name"], 75)
    address_type = format_string(row.get("Client Address Type", ""), 3)
    address = format_string(row["Client Address"], 50)
    number = format_string(row["Client Number"], 10)
    complement = format_string(row.get("Client Address Complement", ""), 30)
    neighborhood = format_string(row["Client Neighborhood"], 30)
    city = format_string(row["Client City"], 50)
    state = format_string(row["Client State"], 2)
    zip_code = format_numeric(row["Client ZIP"], 8)
    email = format_string(row["Client Email"], 75)
    service_description = format_description(row["Service Description"])

    return (
        "2"
        + rps_type
        + rps_series
        + rps_number
        + issue_date
        + status
        + service_value
        + deduction_value
        + service_code
        + iss_rate
        + iss_retained
        + cpf_cnpj_indicator
        + tomador_document.rjust(14, "0")
        + municipal_reg
        + state_registration
        + name
        + address_type
        + address
        + number
        + complement
        + neighborhood
        + city
        + state
        + zip_code
        + email
        + service_description
    )


def build_footer(total_records: int, total_service_cents: int, total_deduction_cents: int) -> str:
    return (
        "9"
        + format_numeric(str(total_records), 7)
        + format_numeric(str(total_service_cents), 15)
        + format_numeric(str(total_deduction_cents), 15)
    )


def get_output_path_for_xlsx(xlsx_path: str | Path) -> Path:
    return Path(xlsx_path).resolve().with_suffix(".txt")


def generate_txt_from_xlsx(xlsx_path: str | Path, municipal_registration: str, open_after_save: bool = True) -> Path:
    xlsx_path = Path(xlsx_path).resolve()
    output_path = get_output_path_for_xlsx(xlsx_path)
    municipal_registration = save_municipal_registration(municipal_registration)
    df = read_excel(str(xlsx_path))
    warn_about_xlsx_corrections(df)
    create_txt(output_path.as_posix(), df, municipal_registration)
    save_open_after_save_preference(open_after_save)
    if open_after_save:
        open_file_in_default_app(output_path)
    return output_path


def open_file_in_default_app(path: str | Path) -> None:
    file_path = Path(path).resolve()
    if not file_path.exists():
        return

    try:
        if hasattr(os, "startfile"):
            try:
                os.startfile(str(file_path))
                return
            except Exception:
                pass

        if os.name == "nt":
            subprocess.Popen(["notepad.exe", str(file_path)], shell=False)
            return

        if os.name == "posix":
            command = ["open", str(file_path)] if sys.platform == "darwin" else ["xdg-open", str(file_path)]
            subprocess.Popen(command)
            return
    except Exception:
        pass


def prompt_for_xlsx_file() -> str:
    if filedialog is None:
        raise RuntimeError(
            "Tkinter não está disponível para selecionar um arquivo Excel.")

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return filedialog.askopenfilename(
            title="Selecione o arquivo Excel (.xlsx)",
            filetypes=[("Arquivos Excel", "*.xlsx"),
                       ("Todos os arquivos", "*.*")],
        )
    finally:
        root.destroy()


def run_receipt_import_gui() -> None:
    if tk is None or filedialog is None or messagebox is None:
        raise RuntimeError(
            "Tkinter não está disponível para importar arquivos pela interface gráfica."
        )

    root = tk.Tk()
    root.title("Importar recibos e gerar XLSX/TXT RPS")
    root.geometry("620x315")
    root.resizable(False, False)

    txt_path_var = tk.StringVar()
    municipal_registration_var = tk.StringVar(value=load_municipal_registration())
    status_var = tk.StringVar(value="Selecione um arquivo TXT de recibos.")
    open_after_save = tk.BooleanVar(value=load_open_after_save_preference())
    imported_data = {"dataframe": None}

    tk.Label(root, text="Arquivo TXT de recibos:").pack(
        anchor="w", padx=12, pady=(12, 0)
    )
    path_entry = tk.Entry(root, textvariable=txt_path_var, width=78, state="readonly")
    path_entry.pack(anchor="w", padx=12, pady=(3, 8))

    tk.Label(root, text="Inscrição municipal do prestador:").pack(
        anchor="w", padx=12
    )
    tk.Entry(
        root,
        textvariable=municipal_registration_var,
        width=24,
    ).pack(anchor="w", padx=12, pady=(3, 8))

    tk.Label(root, text="Primeiro número do RPS:").pack(
        anchor="w", padx=12
    )
    first_rps_number_var = tk.StringVar(
        value=str(load_last_rps_number() + 1)
    )
    tk.Entry(
        root,
        textvariable=first_rps_number_var,
        width=12,
    ).pack(anchor="w", padx=12, pady=(3, 8))

    def import_txt():
        txt_path = filedialog.askopenfilename(
            title="Selecione o arquivo TXT de recibos",
            filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")],
        )
        if not txt_path:
            return
        try:
            dataframe = extract_receipts(read_text_file(txt_path))
            if dataframe.empty:
                raise ValueError("Nenhum recibo foi encontrado no arquivo TXT.")
            imported_data["dataframe"] = dataframe
            txt_path_var.set(txt_path)
            status_var.set(f"{len(dataframe)} recibo(s) importado(s). Pronto para gerar o XLSX.")
        except Exception as error:
            imported_data["dataframe"] = None
            messagebox.showerror("Erro ao importar TXT", str(error), parent=root)

    def generate_xlsx():
        dataframe = imported_data["dataframe"]
        municipal_registration = municipal_registration_var.get().strip()
        if dataframe is None:
            messagebox.showwarning(
                "Importação necessária",
                "Clique em 'Importar arquivo TXT' antes de gerar o XLSX.",
                parent=root,
            )
            return
        if not municipal_registration:
            messagebox.showwarning(
                "Inscrição municipal necessária",
                "Informe a inscrição municipal do prestador antes de gerar os arquivos.",
                parent=root,
            )
            return
        try:
            first_rps_number = int(first_rps_number_var.get().strip())
            if first_rps_number < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Número de RPS inválido",
                "Informe um número inicial de RPS inteiro e maior que zero.",
                parent=root,
            )
            return
        default_name = f"{Path(txt_path_var.get()).stem}_rps.xlsx"
        xlsx_path = filedialog.asksaveasfilename(
            title="Salvar planilha XLSX",
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Planilhas Excel", "*.xlsx")],
        )
        if not xlsx_path:
            return
        try:
            municipal_registration = save_municipal_registration(
                municipal_registration
            )
            dataframe = assign_rps_numbers(dataframe, first_rps_number)
            dataframe.to_excel(xlsx_path, index=False, engine="openpyxl")
            txt_path = generate_txt_from_xlsx(
                xlsx_path,
                municipal_registration,
                open_after_save=False,
            )
            if open_after_save.get():
                open_file_in_default_app(xlsx_path)
                open_file_in_default_app(txt_path)
            status_var.set(f"XLSX e TXT gerados na mesma pasta: {xlsx_path}")
            messagebox.showinfo(
                "Concluído",
                f"Arquivos criados com sucesso!\n\nXLSX: {xlsx_path}\nTXT: {txt_path}",
                parent=root,
            )
        except Exception as error:
            messagebox.showerror("Erro ao gerar XLSX", str(error), parent=root)

    tk.Checkbutton(
        root,
        text="Abrir arquivos após salvar",
        variable=open_after_save,
        anchor="w",
    ).pack(anchor="w", padx=12, pady=(0, 8))

    buttons_frame = tk.Frame(root)
    buttons_frame.pack(anchor="w", padx=12, pady=(4, 12))
    tk.Button(
        buttons_frame,
        text="Importar arquivo TXT",
        command=import_txt,
        width=24,
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        buttons_frame,
        text="Gerar XLSX e TXT RPS",
        command=generate_xlsx,
        width=24,
    ).pack(side="left")
    tk.Label(root, textvariable=status_var, anchor="w").pack(
        fill="x", padx=12, pady=(0, 10)
    )

    root.mainloop()


def prompt_for_municipal_registration() -> str:
    if tk is None or messagebox is None:
        raise RuntimeError(
            "Tkinter não está disponível para solicitar a inscrição municipal.")

    root = tk.Tk()
    root.title("Informações para gerar TXT de RPS")
    root.geometry("420x220")
    root.resizable(False, False)

    open_after_save = tk.BooleanVar(value=load_open_after_save_preference())

    tk.Label(root, text="Arquivo Excel (.xlsx):").pack(
        anchor="w", padx=10, pady=(10, 0))
    excel_path_var = tk.StringVar()
    path_entry = tk.Entry(root, textvariable=excel_path_var, width=52)
    path_entry.pack(anchor="w", padx=10, pady=(0, 5))

    def choose_file():
        file_path = filedialog.askopenfilename(
            title="Selecione o arquivo Excel (.xlsx)",
            filetypes=[("Arquivos Excel", "*.xlsx"),
                       ("Todos os arquivos", "*.*")],
        )
        if file_path:
            excel_path_var.set(file_path)

    tk.Button(root, text="Selecionar arquivo",
              command=choose_file).pack(anchor="w", padx=10)

    tk.Label(root, text="Inscrição municipal do prestador:").pack(
        anchor="w", padx=10, pady=(10, 0))
    municipal_reg_var = tk.StringVar(value=load_municipal_registration())
    municipal_entry = tk.Entry(root, textvariable=municipal_reg_var, width=20)
    municipal_entry.pack(anchor="w", padx=10, pady=(0, 10))

    result = {"xlsx_path": None, "municipal_registration": None}

    def on_submit():
        excel_path = excel_path_var.get().strip()
        municipal_reg = municipal_reg_var.get().strip()
        if not excel_path:
            messagebox.showerror("Erro", "Informe o caminho do arquivo Excel.")
            return
        if not municipal_reg:
            messagebox.showerror("Erro", "Informe a inscrição municipal.")
            return
        result["xlsx_path"] = excel_path
        result["municipal_registration"] = save_municipal_registration(
            municipal_reg
        )
        root.destroy()

    tk.Checkbutton(
        root,
        text="Abrir arquivos após salvar",
        variable=open_after_save,
        anchor="w",
    ).pack(anchor="w", padx=10, pady=(0, 8))

    tk.Button(root, text="Gerar TXT", command=on_submit).pack(pady=(0, 10))

    root.mainloop()
    if result["xlsx_path"] and result["municipal_registration"]:
        save_open_after_save_preference(open_after_save.get())
    return result["xlsx_path"], result["municipal_registration"]


def resolve_input_path(path: str | None) -> str | None:
    if path:
        return path
    xlsx_path, _ = prompt_for_municipal_registration()
    return xlsx_path


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns_map = {
        "NumeroRPS": "RPS Number",
        "SerieRPS": "RPS Series",
        "TipoRPS": "RPS Type",
        "DataEmissao": "Issue Date",
        "StatusRPS": "Status",
        "ValorServicos": "Service Value",
        "CodigoServico": "Service Code",
        "AliquotaISS": "ISS Rate",
        "CPFCNPJTomador": "Client CPF/CNPJ",
        "RazaoSocialTomador": "Client Name",
        "EnderecoTomador": "Client Address",
        "NumeroTomador": "Client Number",
        "BairroTomador": "Client Neighborhood",
        "CidadeTomador": "Client City",
        "UFTomador": "Client State",
        "CEPTomador": "Client ZIP",
        "EmailTomador": "Client Email",
        "DiscriminacaoServico": "Service Description",
    }

    aliases = {
        "numero rps": "RPS Number",
        "serie rps": "RPS Series",
        "tipo rps": "RPS Type",
        "data emissao": "Issue Date",
        "data de emissao": "Issue Date",
        "status rps": "Status",
        "valor servicos": "Service Value",
        "valor dos servicos": "Service Value",
        "valor deducoes": "Service Deductions",
        "codigo servico": "Service Code",
        "codigo do servico": "Service Code",
        "aliquota iss": "ISS Rate",
        "iss retido": "ISS Retained",
        "cpf cnpj tomador": "Client CPF/CNPJ",
        "cpf cnpj do tomador": "Client CPF/CNPJ",
        "razao social tomador": "Client Name",
        "nome razao social do tomador": "Client Name",
        "tipo logradouro": "Client Address Type",
        "endereco tomador": "Client Address",
        "numero tomador": "Client Number",
        "complemento tomador": "Client Address Complement",
        "bairro tomador": "Client Neighborhood",
        "cidade tomador": "Client City",
        "uf tomador": "Client State",
        "cep tomador": "Client ZIP",
        "email tomador": "Client Email",
        "discriminacao servico": "Service Description",
    }

    def normalized_header(value: object) -> str:
        text = unicodedata.normalize("NFKD", str(value))
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = re.sub(r"[_/()-]+", " ", text)
        return re.sub(r"\s+", " ", text.replace("\ufeff", "")).strip().lower()

    normalized_aliases = {
        normalized_header(alias): target
        for alias, target in {**columns_map, **aliases}.items()
    }
    rename_map = {
        column: normalized_aliases[normalized_header(column)]
        for column in df.columns
        if normalized_header(column) in normalized_aliases
    }
    df = df.rename(columns=rename_map)

    if "Client Municipal Registration" not in df.columns:
        df["Client Municipal Registration"] = ""

    if "Client Address Type" not in df.columns:
        df["Client Address Type"] = ""

    if "Client Address" not in df.columns:
        df["Client Address"] = ""

    if "Client Address Complement" not in df.columns:
        df["Client Address Complement"] = ""

    if "Client Number" not in df.columns:
        df["Client Number"] = ""

    if "Client Neighborhood" not in df.columns:
        df["Client Neighborhood"] = ""

    if "Client City" not in df.columns:
        df["Client City"] = ""

    if "Client State" not in df.columns:
        df["Client State"] = ""

    if "Client ZIP" not in df.columns:
        df["Client ZIP"] = ""

    if "Client Email" not in df.columns:
        df["Client Email"] = ""

    if "Service Description" not in df.columns:
        df["Service Description"] = ""

    if "Service Deductions" not in df.columns:
        df["Service Deductions"] = ""

    if "ISS Retained" not in df.columns:
        df["ISS Retained"] = ""

    if "Client State Registration" not in df.columns:
        df["Client State Registration"] = ""

    if "RPS Type" in df.columns:
        df["RPS Type"] = df["RPS Type"].apply(
            lambda value: str(value or "").strip().upper()
        )

    if "Status" in df.columns:
        df["Status"] = df["Status"].astype(str).str.strip()
        df["Status"] = df["Status"].replace({"": "T"})

    return df


def validate_columns(df: pd.DataFrame) -> None:
    missing = [col for col in EXPECTED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "A planilha está com colunas faltando. Colunas esperadas: "
            + ", ".join(EXPECTED_COLUMNS)
            + f". Faltando: {', '.join(missing)}"
        )


def warn_about_xlsx_corrections(df: pd.DataFrame) -> None:
    if df.empty:
        return

    invalid_rows = []
    for idx, row in df.iterrows():
        rps_type = str(row.get("RPS Type", "") or "").strip().upper()
        is_invalid = rps_type not in {"RPS", "RPS-M"}
        if is_invalid:
            invalid_rows.append(int(idx) + 1)

    if invalid_rows:
        warnings.warn(
            "Atenção: é necessário corrigir a coluna 'RPS Type' da planilha antes de enviar para a Prefeitura. "
            "O valor deve ser 'RPS' ou 'RPS-M', conforme o layout do RPS. A linha(s) "
            f"{invalid_rows[:5]} foi(ram) identificada(s) com dado(s) inválidos.",
            UserWarning,
            stacklevel=2,
        )


def get_markdown_template() -> str:
    return (
        "# Modelo de Planilha para Lote de RPS da Prefeitura de São Paulo\n\n"
        "| Coluna | Tipo | Formato / Observações |\n"
        "|---|---|---|\n"
        "| RPS Number | Numérico | 1 a 10 dígitos |\n"
        "| RPS Series | Texto | Até 5 caracteres |\n"
        "| RPS Type | Numérico | 1 dígito (ex: 1) |\n"
        "| Issue Date | Data | AAAA-MM-DD ou DD/MM/AAAA |\n"
        "| Status | Texto | T para normal, C para cancelado |\n"
        "| Service Value | Decimal | Valor do serviço, ex: 1234.56 |\n"
        "| Service Code | Numérico | Código do serviço prestado |\n"
        "| ISS Rate | Numérico | Alíquota do ISS em centésimos, ex: 0050 |\n"
        "| Client CPF/CNPJ | Numérico | CPF 11 dígitos ou CNPJ 14 dígitos |\n"
        "| Client Municipal Registration | Texto | Inscrição municipal do tomador, se houver |\n"
        "| Client Name | Texto | Razão social ou nome do tomador |\n"
        "| Client Address | Texto | Logradouro do tomador |\n"
        "| Client Number | Texto | Número do imóvel |\n"
        "| Client Neighborhood | Texto | Bairro do tomador |\n"
        "| Client City | Texto | Cidade do tomador |\n"
        "| Client State | Texto | UF do tomador |\n"
        "| Client ZIP | Numérico | CEP com 8 dígitos |\n"
        "| Client Email | Texto | E-mail do tomador |\n"
        "| Service Description | Texto | Discriminação do serviço |\n"
    )


def create_markdown_template(output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(get_markdown_template())


def create_excel_template(output_path: str) -> None:
    sample_row = {
        "RPS Number": "1",
        "RPS Series": "RPS",
        "RPS Type": "1",
        "Issue Date": "2026-08-06",
        "Status": "T",
        "Service Value": "1234.56",
        "Service Code": "12345",
        "ISS Rate": "0050",
        "Client CPF/CNPJ": "12345678901",
        "Client Municipal Registration": "",
        "Client Name": "Cliente Exemplo",
        "Client Address": "Rua exemplo",
        "Client Number": "100",
        "Client Neighborhood": "Centro",
        "Client City": "São Paulo",
        "Client State": "SP",
        "Client ZIP": "01001000",
        "Client Email": "email@exemplo.com",
        "Service Description": "Serviço de consultoria fiscal",
    }
    df = pd.DataFrame([sample_row], columns=EXPECTED_COLUMNS)
    df.to_excel(output_path, index=False, engine="openpyxl")


def read_excel(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, dtype=str, engine="openpyxl")
    df = df.where(pd.notna(df), "")
    df = normalize_columns(df)
    validate_columns(df)
    return df


def read_text_file(path: str | Path) -> str:
    path = Path(path)
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Não foi possível identificar a codificação de {path.name}.")


def _clean_imported_value(value: str) -> str:
    return " ".join(value.split()).strip(" -*:")


def _extract_imported_field(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _clean_imported_value(match.group(1))
    return ""


def _load_patient_database() -> dict[str, dict[str, str]]:
    if not PATIENT_DATABASE_PATH.exists():
        return {}
    with PATIENT_DATABASE_PATH.open(encoding="utf-8") as database_file:
        patients = json.load(database_file)

    database = {}
    for patient in patients:
        responsible_cpf = clean_digits(patient.get("Client CPF/CNPJ", ""))
        cpf = clean_digits(patient.get("CPF do Paciente", ""))
        name = normalize_text(patient.get("Nome do Paciente", ""))
        if responsible_cpf:
            database[f"cpf:{responsible_cpf}"] = patient
        if cpf:
            database[f"cpf:{cpf}"] = patient
        if name:
            database[f"nome:{name.casefold()}"] = patient
    return database


def _apply_patient_history_template(
    source_description: str,
    patient: dict[str, str],
    patient_name: str = "",
    patient_cpf: str = "",
) -> str:
    """Aplica o modelo de histórico (Fem/Masc) de um registro de paciente já conhecido."""
    sex = patient.get("sexo do paciente")
    if sex not in PATIENT_HISTORY_TEMPLATES:
        return source_description

    template = read_text_file(PATIENT_HISTORY_TEMPLATES[sex])
    patient_name = patient_name or normalize_text(patient.get("Nome do Paciente", ""))
    patient_cpf = patient_cpf or normalize_text(patient.get("CPF do Paciente", ""))
    replacements = {
        '"Nome do Paciente"': patient_name,
        '"CPF Paciente"': patient_cpf,
        '"CPF do Paciente"': patient_cpf,
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    date_matches = list(re.finditer(r"\b\d{2}/\d{2}/\d{4}\b", source_description))
    session_dates = ""
    if date_matches:
        session_dates = source_description[
            date_matches[0].start():date_matches[-1].end()
        ].strip()
    template = re.sub(
        r"(?m)^Sessões realizadas em:[^\n]*",
        f"Sessões realizadas em: {session_dates}",
        template,
    )
    return template


def format_patient_history_for_record(source_description: str, patient: dict[str, str]) -> str:
    """Gera a descrição do serviço a partir de um registro de cliente já selecionado
    (ex.: GUI), usando diretamente o campo 'sexo do paciente' do registro."""
    return _apply_patient_history_template(source_description, patient)


def _format_patient_history(
    source_description: str,
    patient_name: str,
    patient_cpf: str,
    patient_database: dict[str, dict[str, str]],
    responsible_cpf: str = "",
) -> str:
    patient = patient_database.get(f"cpf:{clean_digits(patient_cpf)}")
    if patient is None:
        patient = patient_database.get(f"nome:{patient_name.casefold()}")
    if patient is None and not patient_name and not patient_cpf:
        patient = patient_database.get(f"cpf:{clean_digits(responsible_cpf)}")
    if patient is None:
        return source_description
    return _apply_patient_history_template(source_description, patient, patient_name, patient_cpf)


def _apply_responsible_addresses(df: pd.DataFrame) -> pd.DataFrame:
    patient_database = _load_patient_database()
    address_fields = (
        "Client Address",
        "Client Number",
        "Client Neighborhood",
        "Client City",
        "Client State",
        "Client ZIP",
    )
    for index, row in df.iterrows():
        responsible = patient_database.get(
            f"cpf:{clean_digits(row.get('Client CPF/CNPJ', ''))}"
        )
        if responsible is None:
            continue
        for field in address_fields:
            df.at[index, field] = responsible.get(field, "")
    return df


def _split_receipt_records(text: str) -> list[str]:
    text = text.replace("\r\n", "\n")
    markers = list(re.finditer(
        r"(?im)^(?:\s*\d+\s+)?(?:Nome paciente:|Paciente:)", text
    ))
    markers.extend(
        match
        for match in re.finditer(r"(?im)^[ \t]*Nome responsável:", text)
        if not text[:match.start()].strip()
        or re.search(r"\n[ \t]*\n[ \t]*$", text[:match.start()])
    )
    markers.sort(key=lambda match: match.start())
    if not markers:
        return [text]
    records = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        record = text[marker.start():end].strip()
        if record:
            records.append(record)
    return records


def extract_receipts(text: str) -> pd.DataFrame:
    rows = []
    patient_database = _load_patient_database()
    for record in _split_receipt_records(text):
        value_text = _extract_imported_field(record, [
            r"Valor do recibo:\s*([\d.,]+)",
            r"Valor do recebimento:\s*([\d.,]+)",
            r"Valor:\s*([\d.,]+)",
        ])
        try:
            value = value_text.replace(".", "").replace(",", ".") if value_text else ""
            value = Decimal(value) if value else ""
        except InvalidOperation:
            value = ""

        patient_name = _extract_imported_field(record, [
            r"(?:Nome paciente|Paciente):\s*(.+?)(?=\n|CPF|Nome responsável|Responsável|Pagador|Valor|Data|$)",
        ])
        patient_name = re.sub(r"^Nome:\s*", "", patient_name, flags=re.IGNORECASE).strip()
        patient_cpf = _extract_imported_field(record, [
            r"CPF do paciente:\s*([\d.\-/]+)",
            r"CPF paciente:\s*([\d.\-/]+)",
            r"CPF Paciente:\s*([\d.\-/]+)",
        ])
        responsible_cpf = _extract_imported_field(record, [
            r"CPF do pagador:\s*([\d.\-/]+)",
            r"CPF pagador e responsável:\s*([\d.\-/]+)",
            r"CPF responsável:\s*([\d.\-/]+)",
            r"CPF Responsável:\s*([\d.\-/]+)",
            r"CPF pagador:\s*([\d.\-/]+)",
        ])
        text_address = _extract_imported_field(record, [
            r"Endereço:\s*(.+?)(?=\n\s*(?:E-mail|Valor|Data|Descrição)|$)"
        ])
        responsible = patient_database.get(f"cpf:{clean_digits(responsible_cpf)}")
        address_fields = {
            field: responsible.get(field, "")
            for field in (
                "Client Address",
                "Client Number",
                "Client Neighborhood",
                "Client City",
                "Client State",
                "Client ZIP",
            )
        } if responsible else {
            "Client Address": text_address,
            "Client Number": "",
            "Client Neighborhood": "",
            "Client City": "",
            "Client State": "",
            "Client ZIP": "",
        }
        source_description = _extract_imported_field(record, [
            r"Descrição do serviço prestado:\s*(.+?)(?=\n|={3,}|$)"
        ])

        rows.append({
            "RPS Number": str(len(rows) + 1),
            "RPS Series": "E",
            "RPS Type": "RPS",
            "Issue Date": _extract_imported_field(record, [
                r"Data do recebimento:\s*([\d/]+)", r"Data:\s*([\d/]+)"
            ]),
            "Status": "T",
            "Service Value": value,
            "Service Code": "5118",
            "ISS Rate": "0",
            "Client CPF/CNPJ": responsible_cpf,
            "Client Name": _extract_imported_field(record, [
                r"Nome responsável:\s*(.+?)(?=\n|CPF|E-mail|Endereço|Valor|Data|$)",
                r"Responsável e pagador:\s*(.+?)(?=\n|CPF|E-mail|Endereço|Valor|Data|$)",
                r"Pagador:\s*(.+?)(?=\n|CPF|E-mail|Endereço|Valor|Data|$)",
            ]),
            **address_fields,
            "Client Email": _extract_imported_field(record, [
                r"(?:E-mail|E mail):\s*([^\s]+)"
            ]),
            "Service Description": _format_patient_history(
                source_description,
                patient_name,
                patient_cpf,
                patient_database,
                responsible_cpf,
            ),
        })
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS)


def create_xlsx_from_txt(txt_path: str, xlsx_path: str) -> pd.DataFrame:
    df = extract_receipts(read_text_file(txt_path))
    if df.empty:
        raise ValueError("Nenhum recibo foi encontrado no arquivo TXT.")
    df = assign_next_rps_numbers(df)
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    return df


def create_txt(output_path: str, df: pd.DataFrame, municipal_registration: str) -> None:
    _apply_responsible_addresses(df)
    details = []
    total_service_cents = 0
    total_deduction_cents = 0
    issue_dates = []

    for index, row in df.iterrows():
        detail_line = build_detail(row)
        details.append(detail_line)
        total_service_cents += int(
            format_decimal_to_cents(row["Service Value"], 15))
        total_deduction_cents += int(format_decimal_to_cents(
            row.get("Service Deductions", "0"), 15))
        issue_dates.append(parse_date(row["Issue Date"]))

    if not details:
        raise ValueError("A planilha não contém registros de RPS.")

    start_date = min(issue_dates)
    end_date = max(issue_dates)
    header = build_header(municipal_registration, start_date, end_date)
    footer = build_footer(
        len(details), total_service_cents, total_deduction_cents)

    with open(output_path, "w", encoding="latin-1", errors="replace") as f:
        f.write(header + "\n")
        for line in details:
            f.write(line + "\n")
        f.write(footer + "\n")
    remember_highest_rps_number(df)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera arquivo TXT no Layout 1 de Lote de RPS para município de São Paulo."
    )
    parser.add_argument(
        "xlsx_path",
        nargs="?",
        help="Caminho do arquivo Excel (.xlsx) de entrada com os dados de RPS.",
    )
    parser.add_argument(
        "municipal_registration",
        nargs="?",
        help="Inscrição municipal da empresa emissora (somente dígitos).",
    )
    parser.add_argument(
        "--txt-path",
        help="Converte um TXT de recibos em XLSX e gera o lote TXT de RPS em uma única execução.",
    )
    parser.add_argument(
        "--municipal-registration",
        dest="municipal_registration_option",
        help="Inscrição municipal usada no fluxo integrado do TXT.",
    )
    parser.add_argument(
        "--template-markdown",
        help="Gera um arquivo Markdown de modelo no mesmo diretório do arquivo informado.",
        action="store_true",
    )
    parser.add_argument(
        "--template-excel",
        help="Gera um modelo de planilha Excel (.xlsx) no mesmo diretório do arquivo informado.",
        action="store_true",
    )
    parser.add_argument(
        "--open-after-save",
        dest="open_after_save",
        action="store_true",
        default=load_open_after_save_preference(),
        help="Abre os arquivos gerados após salvar (padrão: ativado).",
    )
    parser.add_argument(
        "--no-open-after-save",
        dest="open_after_save",
        action="store_false",
        help="Não abre os arquivos gerados após salvar.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    municipal_registration = (
        args.municipal_registration_option or args.municipal_registration
    )

    if args.txt_path:
        if not municipal_registration:
            raise ValueError("Informe a inscrição municipal ao usar --txt-path.")
        txt_path = Path(args.txt_path).resolve()
        xlsx_path = txt_path.with_name(f"{txt_path.stem}_rps.xlsx")
        output_path = txt_path.with_suffix(".rps.txt")
        create_xlsx_from_txt(str(txt_path), str(xlsx_path))
        df = read_excel(str(xlsx_path))
        create_txt(str(output_path), df, municipal_registration)
        save_open_after_save_preference(args.open_after_save)
        if args.open_after_save:
            open_file_in_default_app(xlsx_path)
            open_file_in_default_app(output_path)
        print(f"Planilha intermediária gerada: {xlsx_path}")
        print(f"Arquivo RPS gerado: {output_path}")
        return

    if args.template_markdown or args.template_excel:
        if not args.xlsx_path:
            raise ValueError(
                "Informe o caminho base do arquivo para gerar o template.")
        base_path = os.path.abspath(args.xlsx_path)
        if args.template_markdown:
            markdown_path = os.path.splitext(base_path)[0] + "_template.md"
            create_markdown_template(markdown_path)
            print(f"Template Markdown gerado: {markdown_path}")
        if args.template_excel:
            excel_path = os.path.splitext(base_path)[0] + "_template.xlsx"
            create_excel_template(excel_path)
            print(f"Template Excel gerado: {excel_path}")
        return

    if args.xlsx_path and args.municipal_registration:
        xlsx_path = args.xlsx_path
        municipal_registration = args.municipal_registration
    elif not args.xlsx_path and not args.municipal_registration:
        try:
            import gui_ctk
        except ImportError:
            run_receipt_import_gui()
        else:
            gui_ctk.run_app()
        return
    else:
        xlsx_path, municipal_registration = prompt_for_municipal_registration()
        args.open_after_save = load_open_after_save_preference()

    xlsx_path = os.path.abspath(xlsx_path)
    output_path = generate_txt_from_xlsx(xlsx_path, municipal_registration, args.open_after_save)

    print(f"Arquivo gerado: {output_path}")


if __name__ == "__main__":
    main()
