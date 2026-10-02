"""Interface gráfica (CustomTkinter) para cadastrar recibos manualmente, gerar
XLSX/TXT de RPS e gerenciar o cadastro de clientes (clientes.json)."""
from __future__ import annotations

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

import main as core
from clientes_storage import ClientesStorage
from recibos_storage import RecibosStorage
from ui_widgets import DatePickerFrame, MultiDatePickerFrame

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def format_cpf_cnpj_display(value: str) -> str:
    digits = "".join(filter(str.isdigit, str(value or "")))
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return value


class CadastroClientesWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Cadastro de Clientes")
        self.geometry("760x600")

        self.storage = ClientesStorage(core.PATIENT_DATABASE_PATH)
        self.editing_cpf: str | None = None

        self._build_widgets()
        self.load_data()

    def _build_widgets(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text="Gerenciar Clientes", font=("Arial", 20, "bold")
        ).grid(row=0, column=0, pady=20)

        container = ctk.CTkFrame(self)
        container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        form_frame = ctk.CTkScrollableFrame(container, label_text="Dados do Cliente")
        form_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.entries: dict[str, ctk.CTkBaseClass] = {}
        text_fields = [
            ("CPF/CNPJ do Responsável", "Client CPF/CNPJ"),
            ("Nome do Responsável", "Client Name"),
            ("Nome do Paciente", "Nome do Paciente"),
            ("CPF do Paciente", "CPF do Paciente"),
            ("Endereço", "Client Address"),
            ("Número", "Client Number"),
            ("Bairro", "Client Neighborhood"),
            ("Cidade", "Client City"),
            ("UF", "Client State"),
            ("CEP", "Client ZIP"),
            ("E-mail", "Client Email"),
        ]
        for label, key in text_fields:
            ctk.CTkLabel(form_frame, text=label).pack(anchor="w", padx=5)
            entry = ctk.CTkEntry(form_frame)
            entry.pack(fill="x", padx=5, pady=(0, 10))
            self.entries[key] = entry

        ctk.CTkLabel(form_frame, text="Sexo do Paciente").pack(anchor="w", padx=5)
        sexo_cb = ctk.CTkComboBox(form_frame, values=["Fem", "Masc"])
        sexo_cb.pack(fill="x", padx=5, pady=(0, 10))
        sexo_cb.set("")
        self.entries["sexo do paciente"] = sexo_cb

        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        self.btn_save = ctk.CTkButton(
            btn_frame, text="Salvar Cliente", command=self.save, fg_color="green"
        )
        self.btn_save.pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(
            btn_frame, text="Novo Cadastro", command=self.clear_form, fg_color="gray"
        ).pack(side="left", padx=5, expand=True, fill="x")

        list_frame = ctk.CTkFrame(container)
        list_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(list_frame, text="Clientes Cadastrados").pack(pady=5)
        self.list_scroll = ctk.CTkScrollableFrame(list_frame)
        self.list_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    def load_data(self) -> None:
        for widget in self.list_scroll.winfo_children():
            widget.destroy()

        for cliente in self.storage.load_clientes():
            item = ctk.CTkFrame(self.list_scroll)
            item.pack(fill="x", pady=2)

            cpf_fmt = format_cpf_cnpj_display(cliente.get("Client CPF/CNPJ", ""))
            label_text = f"{cliente.get('Client Name', '')} ({cpf_fmt})"
            ctk.CTkLabel(item, text=label_text, anchor="w").pack(
                side="left", padx=5, fill="x", expand=True
            )
            ctk.CTkButton(
                item, text="X", width=30, fg_color="red",
                command=lambda c=cliente: self.delete(c),
            ).pack(side="right", padx=2)
            ctk.CTkButton(
                item, text="E", width=30,
                command=lambda c=cliente: self.edit(c),
            ).pack(side="right", padx=2)

    def _read_form(self) -> dict[str, str]:
        return {key: widget.get().strip() for key, widget in self.entries.items()}

    def save(self) -> None:
        data = self._read_form()
        if not data.get("Client Name"):
            messagebox.showerror("Erro", "Nome do Responsável é obrigatório.", parent=self)
            return
        if not data.get("Client CPF/CNPJ"):
            messagebox.showerror("Erro", "CPF/CNPJ do Responsável é obrigatório.", parent=self)
            return
        if data.get("sexo do paciente") not in ("Fem", "Masc"):
            data["sexo do paciente"] = ""

        try:
            if self.editing_cpf:
                self.storage.update_cliente(self.editing_cpf, data)
                messagebox.showinfo("Sucesso", "Cliente atualizado!", parent=self)
            else:
                self.storage.save_cliente(data)
                messagebox.showinfo("Sucesso", "Cliente cadastrado!", parent=self)
            self.clear_form()
            self.load_data()
        except Exception as error:
            messagebox.showerror("Erro", f"Erro ao salvar: {error}", parent=self)

    def edit(self, cliente: dict[str, str]) -> None:
        self.editing_cpf = cliente.get("Client CPF/CNPJ", "")
        self.btn_save.configure(text="Atualizar Cliente")
        for key, widget in self.entries.items():
            value = cliente.get(key, "")
            if hasattr(widget, "delete"):
                widget.delete(0, "end")
            if hasattr(widget, "set"):
                widget.set(value)
            else:
                widget.insert(0, value)

    def delete(self, cliente: dict[str, str]) -> None:
        if messagebox.askyesno("Confirmar", "Remover este cliente?", parent=self):
            self.storage.delete_cliente(cliente.get("Client CPF/CNPJ", ""))
            self.load_data()

    def clear_form(self) -> None:
        self.editing_cpf = None
        self.btn_save.configure(text="Salvar Cliente")
        for widget in self.entries.values():
            if hasattr(widget, "delete"):
                widget.delete(0, "end")
            if hasattr(widget, "set"):
                widget.set("")


class GerarRPSApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Gerador de Lote RPS - São Paulo")
        self.geometry("1100x680")

        self.recibos_storage = RecibosStorage(core.RECEIPTS_DATABASE_PATH)
        self.recibos: list[dict] = self.recibos_storage.load_recibos()
        self.editing_index: int | None = None
        self.pagador_map: dict[str, dict] = {}
        self.beneficiario_map: dict[str, dict] = {}

        self.municipal_registration_var = ctk.StringVar(
            value=core.load_municipal_registration()
        )
        self.first_rps_number_var = ctk.StringVar(
            value=str(core.load_last_rps_number() + 1)
        )
        self.open_after_save_var = ctk.BooleanVar(
            value=core.load_open_after_save_preference()
        )
        self.status_var = ctk.StringVar(value="Cadastre um recibo para começar.")

        self._build_widgets()
        self.refresh_clientes_options()
        self._refresh_recibos_list()
        if self.recibos:
            self.status_var.set(f"{len(self.recibos)} recibo(s) carregado(s) de recibos.json.")

    def _build_widgets(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            header, text="Gerador de Arquivos RPS - São Paulo",
            font=("Arial", 20, "bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header, text="Cadastro de Clientes", command=self.open_clientes_window,
        ).pack(side="right")

        container = ctk.CTkFrame(self)
        container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        form_frame = ctk.CTkScrollableFrame(container, label_text="Novo Recibo")
        form_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(form_frame, text="Data do recebimento:").pack(anchor="w", padx=5)
        self.data_recibo = DatePickerFrame(form_frame)
        self.data_recibo.pack(fill="x", padx=5, pady=(0, 4))

        ctk.CTkLabel(form_frame, text="Valor (R$):").pack(anchor="w", padx=5)
        self.valor_entry = ctk.CTkEntry(form_frame, placeholder_text="0,00")
        self.valor_entry.pack(fill="x", padx=5, pady=(0, 4))

        ctk.CTkLabel(form_frame, text="CPF Pagador:").pack(anchor="w", padx=5)
        self.cpf_pagador_cb = ctk.CTkComboBox(
            form_frame, values=[], command=self.on_pagador_selected
        )
        self.cpf_pagador_cb.pack(fill="x", padx=5, pady=(0, 4))
        self.cpf_pagador_cb.set("")

        ctk.CTkLabel(form_frame, text="CPF do Beneficiário:").pack(anchor="w", padx=5)
        self.cpf_beneficiario_cb = ctk.CTkComboBox(form_frame, values=[])
        self.cpf_beneficiario_cb.pack(fill="x", padx=5, pady=(0, 4))
        self.cpf_beneficiario_cb.set("")

        ctk.CTkLabel(form_frame, text="Descrição/Observações (Sessões):").pack(
            anchor="w", padx=5
        )
        self.sessoes_picker = MultiDatePickerFrame(form_frame)
        self.sessoes_picker.pack(fill="x", padx=5, pady=(0, 4))

        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=4)
        ctk.CTkButton(
            btn_frame, text="Novo Recibo", command=self.clear_form,
        ).pack(side="left", fill="x", expand=True, padx=(5, 2))
        ctk.CTkButton(
            btn_frame, text="Salvar Recibo", command=self.save_recibo, fg_color="green",
        ).pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkButton(
            btn_frame, text="Limpar Formulário", command=self.clear_form, fg_color="gray",
        ).pack(side="left", fill="x", expand=True, padx=(2, 5))

        list_frame = ctk.CTkFrame(container)
        list_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(list_frame, text="Recibos Salvos").pack(pady=5)
        self.list_scroll = ctk.CTkScrollableFrame(list_frame)
        self.list_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        settings_frame = ctk.CTkFrame(self)
        settings_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        settings_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(settings_frame, text="Inscrição municipal:").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 0)
        )
        ctk.CTkEntry(
            settings_frame, textvariable=self.municipal_registration_var, state="readonly"
        ).grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 10)
        )
        ctk.CTkLabel(settings_frame, text="Primeiro número do RPS:").grid(
            row=0, column=1, sticky="w", padx=10, pady=(10, 0)
        )
        ctk.CTkEntry(settings_frame, textvariable=self.first_rps_number_var).grid(
            row=1, column=1, sticky="ew", padx=10, pady=(0, 10)
        )
        ctk.CTkCheckBox(
            settings_frame, text="Abrir arquivos após salvar",
            variable=self.open_after_save_var,
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
        ctk.CTkButton(
            settings_frame, text="Gerar XLSX e TXT RPS", command=self.generate_files,
            fg_color="green",
        ).grid(row=2, column=1, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            self, textvariable=self.status_var, anchor="w", wraplength=1050
        ).grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))

    def open_clientes_window(self) -> None:
        window = CadastroClientesWindow(self)
        window.grab_set()
        window.focus_force()
        window.protocol(
            "WM_DELETE_WINDOW",
            lambda: (window.destroy(), self.refresh_clientes_options()),
        )

    def refresh_clientes_options(self) -> None:
        clientes = ClientesStorage(core.PATIENT_DATABASE_PATH).load_clientes()

        self.pagador_map = {
            f"{c.get('Client Name', '')} - {format_cpf_cnpj_display(c.get('Client CPF/CNPJ', ''))}": c
            for c in sorted(clientes, key=lambda c: c.get("Client Name", "").casefold())
            if c.get("Client CPF/CNPJ")
        }
        self.cpf_pagador_cb.configure(values=list(self.pagador_map.keys()))

        beneficiarios: dict[str, dict] = {}
        for cliente in sorted(clientes, key=lambda c: c.get("Nome do Paciente", "").casefold()):
            patient_cpf = cliente.get("CPF do Paciente", "")
            if not patient_cpf:
                continue
            label = (
                f"{cliente.get('Nome do Paciente', '')} - "
                f"{format_cpf_cnpj_display(patient_cpf)}"
            )
            beneficiarios[label] = cliente
        self.beneficiario_map = beneficiarios
        self.cpf_beneficiario_cb.configure(values=list(self.beneficiario_map.keys()))

    def on_pagador_selected(self, label: str) -> None:
        cliente = self.pagador_map.get(label)
        if not cliente:
            return
        patient_label = (
            f"{cliente.get('Nome do Paciente', '')} - "
            f"{format_cpf_cnpj_display(cliente.get('CPF do Paciente', ''))}"
        )
        if patient_label in self.beneficiario_map:
            self.cpf_beneficiario_cb.set(patient_label)

    def save_recibo(self) -> None:
        data_recibo = self.data_recibo.get().strip()
        valor = self.valor_entry.get().strip()
        pagador_label = self.cpf_pagador_cb.get().strip()
        beneficiario_label = self.cpf_beneficiario_cb.get().strip()
        descricao = self.sessoes_picker.get().strip()

        if not data_recibo:
            messagebox.showwarning("Data obrigatória", "Informe a data do recebimento.", parent=self)
            return
        if not valor:
            messagebox.showwarning("Valor obrigatório", "Informe o valor do recibo.", parent=self)
            return
        cliente = self.pagador_map.get(pagador_label)
        if not cliente:
            messagebox.showwarning(
                "CPF Pagador obrigatório", "Selecione o CPF do pagador.", parent=self
            )
            return
        if not descricao:
            messagebox.showwarning(
                "Sessões obrigatórias", "Selecione as datas das sessões.", parent=self
            )
            return

        patient_cliente = self.beneficiario_map.get(beneficiario_label, cliente)
        responsible_cpf = cliente.get("Client CPF/CNPJ", "")

        service_description = core.format_patient_history_for_record(
            descricao, patient_cliente
        )

        recibo = {
            "RPS Series": "E",
            "RPS Type": "RPS",
            "Issue Date": data_recibo,
            "Status": "T",
            "Service Value": valor,
            "Service Code": "5118",
            "ISS Rate": "0",
            "Client CPF/CNPJ": responsible_cpf,
            "Client Name": cliente.get("Client Name", ""),
            "Client Address": cliente.get("Client Address", ""),
            "Client Number": cliente.get("Client Number", ""),
            "Client Neighborhood": cliente.get("Client Neighborhood", ""),
            "Client City": cliente.get("Client City", ""),
            "Client State": cliente.get("Client State", ""),
            "Client ZIP": cliente.get("Client ZIP", ""),
            "Client Email": cliente.get("Client Email", ""),
            "Service Description": service_description,
            "_session_dates": list(self.sessoes_picker.selected_dates),
            "_pagador_label": pagador_label,
            "_beneficiario_label": beneficiario_label,
        }

        if self.editing_index is not None:
            self.recibos[self.editing_index] = recibo
        else:
            self.recibos.append(recibo)

        self.recibos_storage.save_recibos(self.recibos)
        self.clear_form()
        self._refresh_recibos_list()
        self.status_var.set(f"{len(self.recibos)} recibo(s) na lista.")

    def _refresh_recibos_list(self) -> None:
        for widget in self.list_scroll.winfo_children():
            widget.destroy()

        for index, recibo in enumerate(self.recibos):
            item = ctk.CTkFrame(self.list_scroll)
            item.pack(fill="x", pady=4)

            label_text = (
                f"Data: {recibo['Issue Date']} | Valor: R$ {recibo['Service Value']} | "
                f"{recibo['Service Description']}"
            )
            ctk.CTkLabel(item, text=label_text, anchor="w", justify="left", wraplength=420).pack(
                anchor="w", padx=5, pady=(5, 0)
            )

            buttons = ctk.CTkFrame(item, fg_color="transparent")
            buttons.pack(anchor="e", padx=5, pady=5)
            ctk.CTkButton(
                buttons, text="Editar", width=80,
                command=lambda i=index: self.edit_recibo(i),
            ).pack(side="left", padx=(0, 5))
            ctk.CTkButton(
                buttons, text="Deletar", width=80, fg_color="red",
                command=lambda i=index: self.delete_recibo(i),
            ).pack(side="left")

    def edit_recibo(self, index: int) -> None:
        recibo = self.recibos[index]
        self.editing_index = index

        self.data_recibo.delete(0, "end")
        self.data_recibo.insert(0, recibo["Issue Date"])
        self.valor_entry.delete(0, "end")
        self.valor_entry.insert(0, recibo["Service Value"])
        self.cpf_pagador_cb.set(recibo.get("_pagador_label", ""))
        self.cpf_beneficiario_cb.set(recibo.get("_beneficiario_label", ""))
        self.sessoes_picker.set_dates(recibo.get("_session_dates", []))

    def delete_recibo(self, index: int) -> None:
        if messagebox.askyesno("Confirmar", "Remover este recibo?", parent=self):
            self.recibos.pop(index)
            self.recibos_storage.save_recibos(self.recibos)
            if self.editing_index == index:
                self.clear_form()
            self._refresh_recibos_list()
            self.status_var.set(f"{len(self.recibos)} recibo(s) na lista.")

    def clear_form(self) -> None:
        self.editing_index = None
        self.data_recibo.delete(0, "end")
        self.valor_entry.delete(0, "end")
        self.cpf_pagador_cb.set("")
        self.cpf_beneficiario_cb.set("")
        self.sessoes_picker.clear()

    def generate_files(self) -> None:
        if not self.recibos:
            messagebox.showwarning(
                "Nenhum recibo", "Cadastre ao menos um recibo antes de gerar os arquivos.",
                parent=self,
            )
            return

        municipal_registration = core.load_municipal_registration().strip()
        self.municipal_registration_var.set(municipal_registration)
        if not municipal_registration:
            messagebox.showwarning(
                "Inscrição municipal necessária",
                "Informe a inscrição municipal do prestador antes de gerar os arquivos.",
                parent=self,
            )
            return
        try:
            first_rps_number = int(self.first_rps_number_var.get().strip())
            if first_rps_number < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Número de RPS inválido",
                "Informe um número inicial de RPS inteiro e maior que zero.",
                parent=self,
            )
            return

        xlsx_path = filedialog.asksaveasfilename(
            title="Salvar planilha XLSX",
            initialfile="recibos_rps.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Planilhas Excel", "*.xlsx")],
        )
        if not xlsx_path:
            return

        try:
            municipal_registration = core.save_municipal_registration(
                municipal_registration
            )
            rows = [
                {key: value for key, value in recibo.items() if not key.startswith("_")}
                for recibo in sorted(
                    self.recibos,
                    key=lambda r: datetime.strptime(r["Issue Date"], "%d/%m/%Y"),
                )
            ]
            dataframe = core.pd.DataFrame(rows, columns=core.EXPECTED_COLUMNS)
            dataframe = core.assign_rps_numbers(dataframe, first_rps_number)
            dataframe.to_excel(xlsx_path, index=False, engine="openpyxl")
            txt_path = core.generate_txt_from_xlsx(
                xlsx_path, municipal_registration, open_after_save=False
            )
            core.save_open_after_save_preference(self.open_after_save_var.get())
            if self.open_after_save_var.get():
                core.open_file_in_default_app(xlsx_path)
                core.open_file_in_default_app(txt_path)
            self.status_var.set(f"XLSX e TXT gerados na mesma pasta: {xlsx_path}")
            messagebox.showinfo(
                "Concluído",
                f"Arquivos criados com sucesso!\n\nXLSX: {xlsx_path}\nTXT: {txt_path}",
                parent=self,
            )
        except Exception as error:
            messagebox.showerror("Erro ao gerar arquivos", str(error), parent=self)


def run_app() -> None:
    app = GerarRPSApp()
    app.mainloop()


if __name__ == "__main__":
    run_app()
