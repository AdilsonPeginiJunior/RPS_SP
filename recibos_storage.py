"""Persistência dos recibos da tela Gerador de RPS em recibos.json e importação de TXT de RPS."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _format_doc(value: str) -> str:
    digits = "".join(filter(str.isdigit, str(value or "")))
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return value


class RecibosStorage:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load_recibos(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as file:
            return json.load(file)

    def save_recibos(self, recibos: list[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(recibos, file, ensure_ascii=False, indent=2)


def parse_rps_txt(text: str) -> list[dict]:
    """Converte as linhas de detalhe (tipo 2) de um TXT de RPS em recibos da GUI."""
    recibos = []
    for line in text.splitlines():
        if not line.startswith("2"):
            continue
        number = line[11:23].lstrip("0")
        date = line[23:31]
        value = int(line[32:47]) / 100
        doc = line[73:87]
        doc = doc[-11:] if line[72] == "1" else doc
        description = line[440:].replace("|", "\n")

        patient = re.search(r"(?:da|do) paciente (.+?)\n", description)
        patient_cpf = re.search(r"CPF Paciente: (\S+)", description)
        sessions = re.search(r"Sessões realizadas em: (.+)", description)
        session_dates = re.findall(r"\d{2}/\d{2}/\d{4}", sessions.group(1)) if sessions else []

        name = line[107:182].strip()
        recibos.append({
            "RPS Number": number,
            "RPS Series": line[6:11].strip(),
            "RPS Type": line[1:6].strip(),
            "Issue Date": f"{date[6:]}/{date[4:6]}/{date[:4]}",
            "Status": line[31],
            "Service Value": f"{value:.2f}".replace(".", ","),
            "Service Code": str(int(line[62:67])),
            "ISS Rate": str(int(line[67:71])),
            "Client CPF/CNPJ": _format_doc(doc),
            "Client Name": name,
            "Client Address": line[185:235].strip(),
            "Client Number": line[235:245].strip(),
            "Client Neighborhood": line[275:305].strip(),
            "Client City": line[305:355].strip(),
            "Client State": line[355:357].strip(),
            "Client ZIP": line[357:365].strip(),
            "Client Email": line[365:440].strip(),
            "Service Description": description.strip(),
            "_session_dates": session_dates,
            "_pagador_label": f"{name} - {_format_doc(doc)}",
            "_beneficiario_label": (
                f"{patient.group(1).strip()} - {patient_cpf.group(1)}"
                if patient and patient_cpf else ""
            ),
        })
    return recibos
