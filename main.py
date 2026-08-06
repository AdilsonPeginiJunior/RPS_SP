import argparse
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

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


def clean_digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value or "")).strip()


def validate_document(value: str) -> str:
    digits = clean_digits(value)
    if len(digits) == 11:
        return digits
    if len(digits) == 14:
        return digits
    raise ValueError(
        f"Documento inválido '{value}': deve conter 11 dígitos para CPF ou 14 dígitos para CNPJ."
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
        + format_numeric(municipal_registration, 8)
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

    tomador_document = validate_document(row["Client CPF/CNPJ"])
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


def prompt_for_municipal_registration() -> str:
    if tk is None or messagebox is None:
        raise RuntimeError(
            "Tkinter não está disponível para solicitar a inscrição municipal.")

    root = tk.Tk()
    root.title("Informações para gerar TXT de RPS")
    root.geometry("420x180")
    root.resizable(False, False)

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
    municipal_reg_var = tk.StringVar()
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
        result["municipal_registration"] = municipal_reg
        root.destroy()

    tk.Button(root, text="Gerar TXT", command=on_submit).pack(pady=(0, 10))

    root.mainloop()
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

    df = df.rename(columns={col: columns_map[col]
                   for col in columns_map if col in df.columns})

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


def create_txt(output_path: str, df: pd.DataFrame, municipal_registration: str) -> None:
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


def main() -> None:
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
        "--template-markdown",
        help="Gera um arquivo Markdown de modelo no mesmo diretório do arquivo informado.",
        action="store_true",
    )
    parser.add_argument(
        "--template-excel",
        help="Gera um modelo de planilha Excel (.xlsx) no mesmo diretório do arquivo informado.",
        action="store_true",
    )
    args = parser.parse_args()

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
    else:
        xlsx_path, municipal_registration = prompt_for_municipal_registration()

    xlsx_path = os.path.abspath(xlsx_path)
    output_path = os.path.splitext(xlsx_path)[0] + ".txt"

    df = read_excel(xlsx_path)
    create_txt(output_path, df, municipal_registration)

    print(f"Arquivo gerado: {output_path}")


if __name__ == "__main__":
    main()
