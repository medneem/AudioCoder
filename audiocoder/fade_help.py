"""Scrollable AudioCoder help: illustrated FFmpeg fade curves.

The main editing window only shows controls; all explanatory graphs live here.
"""
import customtkinter as ctk

from .fade import FADE_CURVES
from .fade_preview import FadePreview
from .ui_style import FONT_FAMILY, BODY_SIZE, apply_body_font


FADE_DESCRIPTIONS = {
    "log": (
        "Быстрое изменение громкости в начале перехода, затем плавное приближение "
        "к полной громкости. Для затухания — обратный характер: большая часть "
        "перехода остаётся достаточно громкой, спад усиливается у конца."
    ),
    "tri": (
        "Линейное изменение амплитуды с постоянной скоростью. Простой, "
        "предсказуемый вариант без выраженного ускорения."
    ),
    "qsin": (
        "Четверть синусоиды: быстрый, но плавный выход на нужную громкость "
        "без резкого излома возле верхней границы."
    ),
    "hsin": (
        "Половина синусоиды: S-образная огибающая, плавные начало и конец "
        "перехода. Подходит для мягкого появления и затухания."
    ),
    "exp": (
        "Экспоненциальный переход: появление долго остаётся очень тихим и "
        "нарастает преимущественно в конце. При затухании громкость быстро "
        "падает в начале перехода."
    ),
    "qua": (
        "Квадратичная кривая: ускоряющееся появление и замедляющееся "
        "затухание, более выраженное по сравнению с линейным."
    ),
    "cub": (
        "Кубическая кривая: ещё сильнее смещает изменение громкости "
        "к концу появления и началу затухания."
    ),
    "ipar": (
        "Обратная парабола: быстро набирает громкость в начале появления, "
        "затем постепенно замедляется; затухание развивается зеркально."
    ),
}


class FadeHelpWindow(ctk.CTkToplevel):
    """Non-modal reference window with an independent diagram for each curve."""

    def __init__(self, master):
        super().__init__(master)
        self.title("AudioCoder — Справка: появление и затухание")
        self.geometry("940x760")
        self.minsize(760, 520)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._diagrams = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)
        self.help_heading = ctk.CTkLabel(
            header, text="Алгоритмы появления и затухания",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"))
        self.help_heading.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header, text="Закрыть", width=90,
            command=self.destroy
        ).grid(row=0, column=1, sticky="e")

        content = ctk.CTkScrollableFrame(self, corner_radius=12)
        content.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        content.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            content,
            text=(
                "Каждый график показывает появление (слева) и затухание "
                "(справа) за условную 1 секунду. Сине-серая линия — уровень "
                "громкости, от 0 до 100%. Для наглядности участки изменения "
                "показаны на интервалах 0–0,2 с и 0,8–1,0 с. "
                "При конвертации и обычном предпрослушивании применяется "
                "длительность, выбранная в главном окне. Появление и затухание "
                "настраиваются отдельно; вариант «Нет» отключает соответствующий "
                "край без изменения другого. При коротком прослушивании от "
                "маркера эффект ограничен длительностью прослушивания."
            ),
            wraplength=825, justify="left", anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(6, 14))

        for number, (curve_id, name) in enumerate(FADE_CURVES.items(), start=1):
            card = ctk.CTkFrame(content, corner_radius=10)
            card.grid(row=number, column=0, sticky="ew", padx=6, pady=(0, 14))
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card, text=f"{number}. {name}   ·   FFmpeg: {curve_id}",
                anchor="w", font=ctk.CTkFont(size=16, weight="bold")
            ).grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 4))
            ctk.CTkLabel(
                card, text=FADE_DESCRIPTIONS[curve_id],
                anchor="w", justify="left", wraplength=790
            ).grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 8))
            preview = FadePreview(card, height=175)
            preview.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 14))
            preview.set_curves(curve_id, curve_id)
            self._diagrams.append(preview)

        apply_body_font(self, excluded=(self.help_heading,))
        self.lift()

    def refresh_theme(self):
        for diagram in self._diagrams:
            diagram.redraw()
