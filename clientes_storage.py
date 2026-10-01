"""CRUD simples sobre clientes.json, usado pela tela de Cadastro de Clientes."""
from __future__ import annotations

import json
from pathlib import Path

CLIENT_FIELDS = [
    "Client CPF/CNPJ",
    "Client Name",
    "Nome do Paciente",
    "CPF do Paciente",
    "Client Address",
    "Client Number",
    "Client Neighborhood",
    "Client City",
    "Client State",
    "Client ZIP",
    "Client Email",
    "sexo do paciente",
]


def _clean_digits(value: str) -> str:
    return "".join(filter(str.isdigit, str(value or "")))


class ClientesStorage:
    """Cada cliente é identificado pelo CPF/CNPJ do responsável (dígitos)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load_clientes(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as file:
            return json.load(file)

    def _save_all(self, clientes: list[dict[str, str]]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(clientes, file, ensure_ascii=False, indent=2)

    def save_cliente(self, data: dict[str, str]) -> None:
        cpf = _clean_digits(data.get("Client CPF/CNPJ", ""))
        if not cpf:
            raise ValueError("Informe o CPF/CNPJ do responsável.")
        clientes = self.load_clientes()
        if any(_clean_digits(c.get("Client CPF/CNPJ", "")) == cpf for c in clientes):
            raise ValueError(f"Já existe um cliente cadastrado com o CPF/CNPJ '{cpf}'.")
        clientes.append({field: data.get(field, "") for field in CLIENT_FIELDS})
        self._save_all(clientes)

    def update_cliente(self, original_cpf: str, data: dict[str, str]) -> None:
        original_cpf = _clean_digits(original_cpf)
        clientes = self.load_clientes()
        for index, cliente in enumerate(clientes):
            if _clean_digits(cliente.get("Client CPF/CNPJ", "")) == original_cpf:
                clientes[index] = {field: data.get(field, "") for field in CLIENT_FIELDS}
                self._save_all(clientes)
                return
        raise ValueError("Cliente não encontrado para atualização.")

    def delete_cliente(self, cpf: str) -> None:
        cpf = _clean_digits(cpf)
        clientes = self.load_clientes()
        remaining = [
            c for c in clientes if _clean_digits(c.get("Client CPF/CNPJ", "")) != cpf
        ]
        self._save_all(remaining)
