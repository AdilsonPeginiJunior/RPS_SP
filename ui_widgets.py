"""Widgets reutilizáveis de data/calendário (adaptados do projeto _escrituracao-carne-leao)."""
from __future__ import annotations

import calendar as _calendar
import tkinter as tk
from datetime import datetime
from typing import Callable

import customtkinter as ctk


class DatePickerFrame(ctk.CTkFrame):
    """Campo de data com calendário suspenso para seleção de um único dia."""

    def __init__(self, parent, on_date_selected: Callable | None = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_date_selected = on_date_selected
        self.selected_date: datetime | None = None
        self.calendar_window: tk.Toplevel | None = None

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", expand=True)

        self.date_entry = ctk.CTkEntry(self.container, placeholder_text="dd/mm/aaaa")
        self.date_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)

        ctk.CTkButton(
            self.container, text="📅", width=40, command=self.open_calendar
        ).pack(side="left")

    def open_calendar(self) -> None:
        if self.calendar_window is not None and self.calendar_window.winfo_exists():
            self.calendar_window.lift()
            return

        self.calendar_window = tk.Toplevel(self.master)
        self.calendar_window.title("Selecionar Data")
        self.calendar_window.geometry("400x400")
        self.calendar_window.resizable(False, False)
        self.calendar_window.protocol("WM_DELETE_WINDOW", self.close_calendar)

        try:
            parts = self.date_entry.get().split("/")
            current_date = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
        except Exception:
            current_date = datetime.now()

        nav_frame = tk.Frame(self.calendar_window, bg="#212121")
        nav_frame.pack(fill="x", padx=5, pady=5)

        self.current_month = tk.IntVar(value=current_date.month)
        self.current_year = tk.IntVar(value=current_date.year)

        tk.Button(nav_frame, text="◀", command=lambda: self.change_month(-1), width=3).pack(side="left")
        self.month_label = tk.Label(nav_frame, text="", width=15, bg="#212121", fg="white")
        self.month_label.pack(side="left", expand=True, padx=5)
        tk.Button(nav_frame, text="▶", command=lambda: self.change_month(1), width=3).pack(side="left")

        calendar_frame = tk.Frame(self.calendar_window, bg="#212121")
        calendar_frame.pack(fill="both", expand=True, padx=5, pady=5)

        for i, day in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]):
            tk.Label(
                calendar_frame, text=day, bg="#212121", fg="white",
                font=("Arial", 10, "bold"), width=5, height=2,
            ).grid(row=0, column=i)

        self.calendar_frame = calendar_frame
        self.update_calendar()

        button_frame = tk.Frame(self.calendar_window, bg="#212121")
        button_frame.pack(fill="x", padx=5, pady=5)
        tk.Button(button_frame, text="Cancelar", command=self.close_calendar, width=15).pack(side="left", padx=2)
        tk.Button(button_frame, text="OK", command=self.confirm_date, width=15).pack(side="left", padx=2)

    def change_month(self, delta: int) -> None:
        month = self.current_month.get() + delta
        year = self.current_year.get()
        if month > 12:
            month, year = 1, year + 1
        elif month < 1:
            month, year = 12, year - 1
        self.current_month.set(month)
        self.current_year.set(year)
        self.update_calendar()

    def update_calendar(self) -> None:
        for widget in self.calendar_frame.grid_slaves():
            if widget.grid_info()["row"] > 0:
                widget.destroy()

        month, year = self.current_month.get(), self.current_year.get()
        months_pt = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                     "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        self.month_label.config(text=f"{months_pt[month]} {year}")

        row = 1
        for week in _calendar.monthcalendar(year, month):
            for col, day in enumerate(week):
                bg = "#212121" if day == 0 else "#2a2a2a"
                text = "" if day == 0 else str(day)
                tk.Button(
                    self.calendar_frame, text=text, bg=bg, fg="white",
                    font=("Arial", 10), width=5, height=2,
                    command=(lambda d=day: self.select_day(d)) if day != 0 else None,
                ).grid(row=row, column=col, padx=1, pady=1)
            row += 1

    def select_day(self, day: int) -> None:
        self.selected_date = datetime(self.current_year.get(), self.current_month.get(), day)
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, self.selected_date.strftime("%d/%m/%Y"))
        self.close_calendar()
        if self.on_date_selected:
            self.on_date_selected(self.selected_date.strftime("%d/%m/%Y"))

    def close_calendar(self) -> None:
        if self.calendar_window:
            self.calendar_window.destroy()
            self.calendar_window = None

    def confirm_date(self) -> None:
        if self.selected_date:
            self.date_entry.delete(0, "end")
            self.date_entry.insert(0, self.selected_date.strftime("%d/%m/%Y"))
        self.close_calendar()

    def get(self) -> str:
        return self.date_entry.get()

    def delete(self, start, end) -> None:
        self.date_entry.delete(start, end)

    def insert(self, index, text) -> None:
        self.date_entry.insert(index, text)


class MultiDatePickerFrame(ctk.CTkFrame):
    """Seleção de várias datas de sessão, gerando a descrição do serviço automaticamente."""

    def __init__(self, parent, on_dates_changed: Callable | None = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_dates_changed = on_dates_changed
        self.selected_dates: list[str] = []
        self.calendar_window: tk.Toplevel | None = None

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.calendar_btn = ctk.CTkButton(
            self.container, text="📅 Selecionar Datas das Sessões",
            command=self.open_calendar, height=30,
        )
        self.calendar_btn.pack(fill="x", pady=(0, 5))

        self.description_entry = ctk.CTkEntry(
            self.container, placeholder_text="Descrição será gerada automaticamente..."
        )
        self.description_entry.pack(fill="x")

    def open_calendar(self) -> None:
        if self.calendar_window is not None and self.calendar_window.winfo_exists():
            self.calendar_window.lift()
            return

        self.calendar_window = tk.Toplevel(self.master)
        self.calendar_window.title("Selecionar Datas das Sessões")
        self.calendar_window.geometry("400x430")
        self.calendar_window.resizable(False, False)
        self.calendar_window.protocol("WM_DELETE_WINDOW", self.close_calendar)

        current_date = datetime.now()
        nav_frame = tk.Frame(self.calendar_window, bg="#212121")
        nav_frame.pack(fill="x", padx=5, pady=5)

        self.current_month = tk.IntVar(value=current_date.month)
        self.current_year = tk.IntVar(value=current_date.year)

        tk.Button(nav_frame, text="◀", command=lambda: self.change_month(-1), width=3).pack(side="left")
        self.month_label = tk.Label(nav_frame, text="", width=15, bg="#212121", fg="white")
        self.month_label.pack(side="left", expand=True, padx=5)
        tk.Button(nav_frame, text="▶", command=lambda: self.change_month(1), width=3).pack(side="left")

        calendar_frame = tk.Frame(self.calendar_window, bg="#212121")
        calendar_frame.pack(fill="both", expand=True, padx=5, pady=5)
        for i, day in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]):
            tk.Label(
                calendar_frame, text=day, bg="#212121", fg="white",
                font=("Arial", 10, "bold"), width=5, height=2,
            ).grid(row=0, column=i)
        self.calendar_frame = calendar_frame

        info_frame = tk.Frame(self.calendar_window, bg="#212121")
        info_frame.pack(fill="x", padx=5, pady=5)
        tk.Label(info_frame, text="Datas selecionadas:", bg="#212121", fg="white").pack(side="left")
        self.info_label = tk.Label(
            info_frame, text="", bg="#212121", fg="yellow", wraplength=380, justify="left"
        )
        self.info_label.pack(side="left", padx=10)

        button_frame = tk.Frame(self.calendar_window, bg="#212121")
        button_frame.pack(fill="x", padx=5, pady=5)
        tk.Button(button_frame, text="Limpar Seleção", command=self.clear_selection, width=15).pack(side="left", padx=2)
        tk.Button(button_frame, text="Cancelar", command=self.close_calendar, width=15).pack(side="left", padx=2)
        tk.Button(button_frame, text="OK", command=self.confirm_dates, width=15).pack(side="left", padx=2)

        self.update_calendar()

    def change_month(self, delta: int) -> None:
        month = self.current_month.get() + delta
        year = self.current_year.get()
        if month > 12:
            month, year = 1, year + 1
        elif month < 1:
            month, year = 12, year - 1
        self.current_month.set(month)
        self.current_year.set(year)
        self.update_calendar()

    def update_calendar(self) -> None:
        for widget in self.calendar_frame.grid_slaves():
            if widget.grid_info()["row"] > 0:
                widget.destroy()

        month, year = self.current_month.get(), self.current_year.get()
        months_pt = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                     "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        self.month_label.config(text=f"{months_pt[month]} {year}")

        row = 1
        for week in _calendar.monthcalendar(year, month):
            for col, day in enumerate(week):
                if day == 0:
                    bg, text, cmd = "#212121", "", None
                else:
                    date_str = f"{day:02d}/{month:02d}/{year}"
                    bg = "#4a4a4a" if date_str in self.selected_dates else "#2a2a2a"
                    text = str(day)
                    cmd = lambda d=day: self.select_day(d)
                tk.Button(
                    self.calendar_frame, text=text, bg=bg, fg="white",
                    font=("Arial", 10), width=5, height=2, command=cmd,
                ).grid(row=row, column=col, padx=1, pady=1)
            row += 1

        if hasattr(self, "info_label"):
            self.info_label.config(text=", ".join(self.selected_dates) or "Nenhuma")

    def select_day(self, day: int) -> None:
        month, year = self.current_month.get(), self.current_year.get()
        date_str = f"{day:02d}/{month:02d}/{year}"
        if date_str in self.selected_dates:
            self.selected_dates.remove(date_str)
        else:
            self.selected_dates.append(date_str)
        self.selected_dates.sort(key=lambda value: datetime.strptime(value, "%d/%m/%Y"))
        self.update_calendar()

    def clear_selection(self) -> None:
        self.selected_dates = []
        self.update_calendar()

    def close_calendar(self) -> None:
        if self.calendar_window:
            self.calendar_window.destroy()
            self.calendar_window = None

    def confirm_dates(self) -> None:
        self.generate_description()
        self.close_calendar()

    def generate_description(self) -> None:
        self.description_entry.delete(0, "end")
        if not self.selected_dates:
            if self.on_dates_changed:
                self.on_dates_changed("")
            return

        count = len(self.selected_dates)
        if count == 1:
            description = (
                f"Referente a 01 sessão de psicoterapia realizada no dia {self.selected_dates[0]}."
            )
        else:
            dates_text = ", ".join(self.selected_dates[:-1]) + f" e {self.selected_dates[-1]}"
            description = (
                f"Referente a {count:02d} sessões de psicoterapia realizadas nos dias {dates_text}."
            )

        self.description_entry.insert(0, description)
        if self.on_dates_changed:
            self.on_dates_changed(description)

    def get(self) -> str:
        return self.description_entry.get()

    def set_dates(self, dates: list[str]) -> None:
        self.selected_dates = sorted(dates, key=lambda value: datetime.strptime(value, "%d/%m/%Y"))
        self.generate_description()

    def clear(self) -> None:
        self.selected_dates = []
        self.description_entry.delete(0, "end")
