from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import sys
import traceback
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk
from PIL.PngImagePlugin import PngInfo

from face_grid_core import FaceRegion, detect_faces, render_regions

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


APP_TITLE = "Face Grid Stamper"
PALETTE = {
    "ink": "#10131a",
    "panel": "#171c26",
    "panel_alt": "#202735",
    "paper": "#f4f1e8",
    "muted": "#9aa5b5",
    "yellow": "#ffe14d",
    "cyan": "#3ee6ff",
    "lime": "#a3e635",
    "orange": "#fb923c",
}
SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
MODE_LABELS = {"grid": "격자", "keep": "유지", "erase": "가림"}
MODE_COLORS = {"grid": "#22c55e", "keep": "#f59e0b", "erase": "#ef4444"}
DEFAULT_SETTINGS = {
    "spacing": 11.0,
    "thickness": 1.15,
    "opacity": 235.0,
    "margin": 6.0,
    "threshold": 0.72,
    "grid_color": "#0b1830",
}


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


@dataclass
class Document:
    path: Path
    image: Image.Image
    regions: list[FaceRegion] = field(default_factory=list)


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent,
        *,
        text: str,
        command,
        fill: str = PALETTE["panel_alt"],
        hover: str = "#303a4d",
        foreground: str = PALETTE["paper"],
        canvas_background: str = PALETTE["ink"],
        height: int = 36,
    ) -> None:
        self.text = text
        self.command = command
        self.normal_fill = fill
        self.hover_fill = hover
        self.current_fill = fill
        self.foreground = foreground
        self.button_font = tkfont.Font(family="Malgun Gothic", size=9, weight="bold")
        requested_width = max(92, self.button_font.measure(text) + 30)
        super().__init__(
            parent,
            width=requested_width,
            height=height,
            background=canvas_background,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._invoke)

    def set_text(self, text: str) -> None:
        self.text = text
        self._draw()

    def _enter(self, _event=None) -> None:
        self.current_fill = self.hover_fill
        self._draw()

    def _leave(self, _event=None) -> None:
        self.current_fill = self.normal_fill
        self._draw()

    def _invoke(self, event) -> None:
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.command()

    def _draw(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        render_scale = 4
        button_bitmap = Image.new(
            "RGB",
            (width * render_scale, height * render_scale),
            self.cget("background"),
        )
        drawing = ImageDraw.Draw(button_bitmap)
        drawing.rounded_rectangle(
            (1 * render_scale, 1 * render_scale, (width - 1) * render_scale, (height - 1) * render_scale),
            radius=min(11, height // 2) * render_scale,
            fill=self.current_fill,
        )
        button_bitmap = button_bitmap.resize((width, height), Image.Resampling.LANCZOS)
        self.button_image = ImageTk.PhotoImage(button_bitmap)
        self.create_image(0, 0, image=self.button_image, anchor="nw")
        self.create_text(width / 2, height / 2, text=self.text, fill=self.foreground, font=self.button_font)


class FaceGridApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x820")
        self.root.minsize(960, 650)
        self.root.configure(background=PALETTE["ink"])
        self._set_window_icon()

        self.documents: list[Document] = []
        self.current_index: int | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.display_scale = 1.0
        self.display_origin = (0.0, 0.0)
        self.add_region_mode = False
        self.drag_start: tuple[float, float] | None = None
        self.drag_preview_id: int | None = None
        self.render_job: str | None = None
        self.model_path = resource_path("models/face_detection_yunet_2023mar.onnx")

        self.spacing = tk.DoubleVar(value=DEFAULT_SETTINGS["spacing"])
        self.thickness = tk.DoubleVar(value=DEFAULT_SETTINGS["thickness"])
        self.opacity = tk.DoubleVar(value=DEFAULT_SETTINGS["opacity"])
        self.margin = tk.DoubleVar(value=DEFAULT_SETTINGS["margin"])
        self.threshold = tk.DoubleVar(value=DEFAULT_SETTINGS["threshold"])
        self.grid_color = DEFAULT_SETTINGS["grid_color"]
        self.status = tk.StringVar(value="이미지를 열거나 창에 끌어놓으세요.")

        self._configure_styles()
        self._build_ui()
        self._bind_dnd()
        self.root.after(100, self._redraw)

    def _set_window_icon(self) -> None:
        icon = tk.PhotoImage(width=32, height=32)
        icon.put(PALETTE["yellow"], to=(0, 0, 32, 32))
        icon.put(PALETTE["cyan"], to=(0, 0, 9, 9))
        for offset in range(-24, 33, 8):
            for step in range(32):
                x = offset + step
                if 0 <= x < 32:
                    icon.put(PALETTE["ink"], (x, step))
                x = offset + (31 - step)
                if 0 <= x < 32:
                    icon.put(PALETTE["ink"], (x, step))
        self.window_icon = icon
        self.root.iconphoto(True, icon)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        font = ("Malgun Gothic", 10)
        bold = ("Malgun Gothic", 10, "bold")
        style.configure("TFrame", background=PALETTE["ink"])
        style.configure("Card.TFrame", background=PALETTE["panel"])
        style.configure("Header.TFrame", background=PALETTE["ink"])
        style.configure("TLabel", background=PALETTE["ink"], foreground=PALETTE["paper"], font=font)
        style.configure("Title.TLabel", font=("Malgun Gothic", 23, "bold"), foreground=PALETTE["paper"])
        style.configure("Subtitle.TLabel", font=("Malgun Gothic", 9), foreground=PALETTE["muted"])
        style.configure(
            "Tag.TLabel",
            font=("Malgun Gothic", 9, "bold"),
            foreground=PALETTE["cyan"],
            background=PALETTE["ink"],
            padding=(0, 2),
        )
        style.configure(
            "Section.TLabel",
            font=("Malgun Gothic", 11, "bold"),
            foreground=PALETTE["paper"],
            background=PALETTE["panel"],
            padding=(2, 7),
        )
        style.configure("Card.TLabel", background=PALETTE["panel"], foreground=PALETTE["paper"], font=font)
        style.configure("Muted.Card.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Malgun Gothic", 9))

        common_button = {
            "font": bold,
            "padding": (12, 7),
            "borderwidth": 2,
            "relief": "solid",
        }
        style.configure("TButton", background=PALETTE["panel_alt"], foreground=PALETTE["paper"], **common_button)
        style.map("TButton", background=[("active", "#303a4d"), ("pressed", PALETTE["cyan"])], foreground=[("pressed", PALETTE["ink"])])
        style.configure("Primary.TButton", background=PALETTE["yellow"], foreground=PALETTE["ink"], **common_button)
        style.map("Primary.TButton", background=[("active", "#fff07f"), ("pressed", PALETTE["orange"])])
        style.configure("Cyan.TButton", background=PALETTE["cyan"], foreground=PALETTE["ink"], **common_button)
        style.map("Cyan.TButton", background=[("active", "#8ff1ff"), ("pressed", PALETTE["lime"])])
        style.configure("Small.TButton", padding=(9, 5), font=("Malgun Gothic", 9, "bold"))

        style.configure(
            "Card.TLabelframe",
            background=PALETTE["panel"],
            bordercolor=PALETTE["ink"],
            lightcolor=PALETTE["ink"],
            darkcolor=PALETTE["ink"],
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=PALETTE["panel"],
            foreground=PALETTE["yellow"],
            font=("Malgun Gothic", 11, "bold"),
            padding=(8, 4),
        )
        style.configure(
            "Detector.TLabelframe.Label",
            background=PALETTE["cyan"],
            foreground=PALETTE["ink"],
            font=("Malgun Gothic", 11, "bold"),
            padding=(8, 4),
        )
        style.configure("Accent.Horizontal.TScale", background=PALETTE["panel"], troughcolor=PALETTE["panel_alt"])
        style.configure("TPanedwindow", background=PALETTE["ink"])
        style.configure(
            "Status.TLabel",
            background=PALETTE["panel_alt"],
            foreground=PALETTE["cyan"],
            font=("Malgun Gothic", 9, "bold"),
            padding=(10, 6),
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="Header.TFrame")
        header.pack(fill="x", pady=(0, 12))
        title_block = ttk.Frame(header, style="Header.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="AI REFERENCE TOOL", style="Tag.TLabel").pack(anchor="w")
        ttk.Label(title_block, text="FACE GRID / STAMPER", style="Title.TLabel").pack(anchor="w", pady=(5, 0))
        ttk.Label(
            title_block,
            text="캐릭터 시트의 얼굴만 빠르게 표시하고 원본 옆에 안전하게 저장합니다.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(1, 0))

        save_actions = ttk.Frame(header, style="Header.TFrame")
        save_actions.pack(side="right", anchor="se", padx=(20, 0))
        youtube_link = tk.Label(
            save_actions,
            text="YouTube  @toobusyAI  ↗",
            background=PALETTE["ink"],
            foreground=PALETTE["orange"],
            font=("Malgun Gothic", 9, "bold"),
            cursor="hand2",
            padx=8,
        )
        youtube_link.pack(side="top", anchor="e", pady=(0, 8))
        youtube_link.bind("<Button-1>", lambda _event: webbrowser.open("https://www.youtube.com/@toobusyAI"))
        action_row = ttk.Frame(save_actions, style="Header.TFrame")
        action_row.pack(side="top")
        RoundedButton(
            action_row,
            text="다른 곳에 저장",
            command=self.save_to_folder,
            fill="#263140",
            hover="#35445a",
            canvas_background=PALETTE["ink"],
        ).pack(side="left", padx=(0, 7))
        RoundedButton(
            action_row,
            text="저장  →  원본 옆",
            command=self.save_next_to_sources,
            fill=PALETTE["yellow"],
            hover="#fff08a",
            foreground=PALETTE["ink"],
            canvas_background=PALETTE["ink"],
        ).pack(side="left")

        toolbar = ttk.Frame(outer, style="Card.TFrame", padding=7)
        toolbar.pack(fill="x", pady=(0, 10))
        RoundedButton(
            toolbar,
            text="+ 이미지 열기",
            command=self.open_files,
            fill=PALETTE["cyan"],
            hover="#8ff1ff",
            foreground=PALETTE["ink"],
            canvas_background=PALETTE["panel"],
        ).pack(side="left")
        RoundedButton(toolbar, text="얼굴 자동 검출", command=self.detect_current, canvas_background=PALETTE["panel"]).pack(side="left", padx=6)
        self.add_button = RoundedButton(toolbar, text="영역 직접 추가", command=self.toggle_add_mode, canvas_background=PALETTE["panel"])
        self.add_button.pack(side="left")
        RoundedButton(toolbar, text="전체 격자", command=lambda: self.set_all_modes("grid"), canvas_background=PALETTE["panel"]).pack(side="left", padx=(5, 0))
        RoundedButton(toolbar, text="전체 유지", command=lambda: self.set_all_modes("keep"), canvas_background=PALETTE["panel"]).pack(side="left", padx=5)
        ttk.Label(toolbar, text="클릭: 모드 변경  ·  우클릭: 영역 삭제", style="Muted.Card.TLabel").pack(side="right", padx=8)

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=245, style="Card.TFrame", padding=9)
        center = ttk.Frame(body, padding=(8, 0))
        right = ttk.Frame(body, width=275, style="Card.TFrame", padding=9)
        body.add(left, weight=0)
        body.add(center, weight=1)
        body.add(right, weight=0)

        ttk.Label(left, text="01  작업 이미지", style="Section.TLabel").pack(anchor="w", fill="x")
        self.file_list = tk.Listbox(
            left,
            width=32,
            exportselection=False,
            background=PALETTE["panel_alt"],
            foreground=PALETTE["paper"],
            selectbackground=PALETTE["yellow"],
            selectforeground=PALETTE["ink"],
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            font=("Malgun Gothic", 10),
            activestyle="none",
        )
        self.file_list.pack(fill="both", expand=True, pady=(5, 0))
        self.file_list.bind("<<ListboxSelect>>", self._select_document)

        self.canvas = tk.Canvas(
            center,
            background="#0a0d12",
            highlightthickness=1,
            highlightbackground="#354052",
            highlightcolor=PALETTE["yellow"],
            borderwidth=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._schedule_redraw())
        self.canvas.bind("<Button-1>", self._canvas_down)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_up)
        self.canvas.bind("<Button-3>", self._canvas_right_click)

        settings = ttk.LabelFrame(right, text="02  격자 설정", padding=10, style="Card.TLabelframe")
        settings.pack(fill="x")
        self._add_scale(settings, "간격 (% 얼굴폭)", self.spacing, 5.0, 24.0)
        self._add_scale(settings, "굵기 (% 얼굴폭)", self.thickness, 0.3, 3.0)
        self._add_scale(settings, "불투명도", self.opacity, 40, 255)
        self._add_scale(settings, "얼굴 여백 (%)", self.margin, 0.0, 25.0)
        RoundedButton(settings, text="격자 색상", command=self.choose_color, canvas_background=PALETTE["panel"]).pack(fill="x", pady=(8, 0))
        RoundedButton(settings, text="↺  조절값 기본으로", command=self.reset_settings, canvas_background=PALETTE["panel"]).pack(fill="x", pady=(5, 0))

        detector = ttk.LabelFrame(right, text="03  검출 설정", padding=10, style="Card.TLabelframe")
        detector.configure(labelwidget=ttk.Label(detector, text="03  검출 설정", style="Muted.Card.TLabel"))
        detector.pack(fill="x", pady=(10, 0))
        self._add_scale(detector, "신뢰도", self.threshold, 0.45, 0.95)
        ttk.Label(
            detector,
            text="검출된 얼굴을 클릭하면\n격자 → 유지 → 가림으로 바뀝니다.\n우클릭하면 영역을 삭제합니다.",
            justify="left",
            style="Card.TLabel",
        ).pack(anchor="w", pady=(8, 0))

        ttk.Label(
            right,
            text="가림 모드는 주변색으로 얼굴 타원을 채웁니다.\n복잡한 배경이나 완전한 머리 제거는 수동 보정이 필요합니다.",
            wraplength=240,
            justify="left",
            style="Muted.Card.TLabel",
        ).pack(anchor="w", pady=12)

        status_bar = ttk.Label(outer, textvariable=self.status, style="Status.TLabel", anchor="w")
        status_bar.pack(fill="x", pady=(8, 0))

    def _add_scale(self, parent: ttk.Widget, label: str, variable: tk.Variable, minimum: float, maximum: float) -> None:
        ttk.Label(parent, text=label, style="Card.TLabel").pack(anchor="w", pady=(5, 0))
        scale = ttk.Scale(
            parent,
            from_=minimum,
            to=maximum,
            variable=variable,
            style="Accent.Horizontal.TScale",
            command=lambda _value: self._schedule_redraw(),
        )
        scale.pack(fill="x")

    def _bind_dnd(self) -> None:
        if DND_FILES and hasattr(self.root, "drop_target_register"):
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event) -> None:
        paths = [Path(value) for value in self.root.tk.splitlist(event.data)]
        self.add_paths(paths)

    def open_files(self) -> None:
        names = filedialog.askopenfilenames(
            title="캐릭터 시트 또는 이미지 선택",
            filetypes=[("이미지", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff")],
        )
        self.add_paths(Path(name) for name in names)

    def add_paths(self, paths) -> None:
        added = 0
        existing = {doc.path.resolve() for doc in self.documents}
        for path in paths:
            path = Path(path)
            if path.suffix.lower() not in SUPPORTED or not path.exists() or path.resolve() in existing:
                continue
            try:
                image = Image.open(path).convert("RGBA")
                self.documents.append(Document(path, image))
                self.file_list.insert("end", path.name)
                existing.add(path.resolve())
                added += 1
            except Exception as exc:
                messagebox.showwarning(APP_TITLE, f"{path.name}을 열지 못했습니다.\n{exc}")
        if added:
            index = len(self.documents) - added
            self.file_list.selection_clear(0, "end")
            self.file_list.selection_set(index)
            self.file_list.activate(index)
            self.current_index = index
            self.status.set(f"{added}개 이미지를 추가했습니다. 얼굴 자동 검출을 실행하세요.")
            self._redraw()

    def _select_document(self, _event=None) -> None:
        selected = self.file_list.curselection()
        if not selected:
            return
        self.current_index = int(selected[0])
        self._redraw()

    @property
    def document(self) -> Document | None:
        if self.current_index is None or self.current_index >= len(self.documents):
            return None
        return self.documents[self.current_index]

    def detect_current(self) -> None:
        doc = self.document
        if not doc:
            return
        self.status.set("얼굴을 검출하는 중입니다...")
        self.root.update_idletasks()
        try:
            doc.regions = detect_faces(doc.image, self.model_path, self.threshold.get())
            if doc.regions:
                self.status.set(f"얼굴 {len(doc.regions)}개를 찾았습니다. 클릭하여 처리 방식을 바꿀 수 있습니다.")
            else:
                self.status.set("얼굴을 찾지 못했습니다. '영역 직접 추가'로 얼굴을 드래그하세요.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            self.status.set("얼굴 검출에 실패했습니다.")
        self._redraw()

    def set_all_modes(self, mode: str) -> None:
        doc = self.document
        if not doc:
            return
        for region in doc.regions:
            region.mode = mode
        self._redraw()

    def choose_color(self) -> None:
        _rgb, value = colorchooser.askcolor(self.grid_color, title="격자 색상")
        if value:
            self.grid_color = value
            self._schedule_redraw()

    def reset_settings(self) -> None:
        self.spacing.set(DEFAULT_SETTINGS["spacing"])
        self.thickness.set(DEFAULT_SETTINGS["thickness"])
        self.opacity.set(DEFAULT_SETTINGS["opacity"])
        self.margin.set(DEFAULT_SETTINGS["margin"])
        self.threshold.set(DEFAULT_SETTINGS["threshold"])
        self.grid_color = DEFAULT_SETTINGS["grid_color"]
        self.status.set("격자와 검출 조절값을 기본값으로 되돌렸습니다.")
        self._schedule_redraw()

    def toggle_add_mode(self) -> None:
        self.add_region_mode = not self.add_region_mode
        self.add_button.set_text("드래그해서 얼굴 지정" if self.add_region_mode else "영역 직접 추가")
        self.status.set("얼굴 주위를 드래그하세요." if self.add_region_mode else "직접 추가 모드를 종료했습니다.")

    def _image_point(self, event) -> tuple[float, float]:
        ox, oy = self.display_origin
        return ((event.x - ox) / self.display_scale, (event.y - oy) / self.display_scale)

    def _region_at(self, image_x: float, image_y: float) -> FaceRegion | None:
        doc = self.document
        if not doc:
            return None
        matches = [region for region in doc.regions if region.contains(image_x, image_y)]
        return min(matches, key=lambda item: item.width * item.height) if matches else None

    def _canvas_down(self, event) -> None:
        if not self.document:
            return
        if self.add_region_mode:
            self.drag_start = self._image_point(event)
            return
        point = self._image_point(event)
        region = self._region_at(*point)
        if region:
            region.cycle_mode()
            self.status.set(f"선택 영역: {MODE_LABELS[region.mode]}")
            self._redraw()

    def _canvas_drag(self, event) -> None:
        if not self.add_region_mode or not self.drag_start:
            return
        if self.drag_preview_id:
            self.canvas.delete(self.drag_preview_id)
        start_x = self.display_origin[0] + self.drag_start[0] * self.display_scale
        start_y = self.display_origin[1] + self.drag_start[1] * self.display_scale
        self.drag_preview_id = self.canvas.create_rectangle(start_x, start_y, event.x, event.y, outline="#38bdf8", width=2)

    def _canvas_up(self, event) -> None:
        if not self.add_region_mode or not self.drag_start or not self.document:
            return
        end = self._image_point(event)
        x1, x2 = sorted((self.drag_start[0], end[0]))
        y1, y2 = sorted((self.drag_start[1], end[1]))
        self.drag_start = None
        if self.drag_preview_id:
            self.canvas.delete(self.drag_preview_id)
            self.drag_preview_id = None
        if x2 - x1 >= 12 and y2 - y1 >= 12:
            self.document.regions.append(FaceRegion(x1, y1, x2 - x1, y2 - y1))
            self.status.set("수동 얼굴 영역을 추가했습니다.")
        self.add_region_mode = False
        self.add_button.set_text("영역 직접 추가")
        self._redraw()

    def _canvas_right_click(self, event) -> None:
        point = self._image_point(event)
        region = self._region_at(*point)
        doc = self.document
        if doc and region:
            doc.regions.remove(region)
            self.status.set("얼굴 영역을 삭제했습니다.")
            self._redraw()

    def _render_current(self) -> Image.Image | None:
        doc = self.document
        if not doc:
            return None
        return render_regions(
            doc.image,
            doc.regions,
            color=self.grid_color,
            opacity=int(round(self.opacity.get())),
            spacing_percent=self.spacing.get(),
            thickness_percent=self.thickness.get(),
            margin_percent=self.margin.get(),
        )

    def _schedule_redraw(self) -> None:
        if self.render_job:
            self.root.after_cancel(self.render_job)
        self.render_job = self.root.after(120, self._redraw)

    def _redraw(self) -> None:
        self.render_job = None
        self.canvas.delete("all")
        rendered = self._render_current()
        doc = self.document
        if rendered is None or doc is None:
            self.canvas.create_text(
                max(10, self.canvas.winfo_width() // 2),
                max(10, self.canvas.winfo_height() // 2),
                text="이미지를 이 창에 끌어놓거나 '이미지 열기'를 누르세요.",
                fill="#d4d4d4",
                font=("Malgun Gothic", 13),
            )
            return

        canvas_w = max(10, self.canvas.winfo_width() - 24)
        canvas_h = max(10, self.canvas.winfo_height() - 24)
        self.display_scale = min(canvas_w / rendered.width, canvas_h / rendered.height, 1.0)
        display_size = (
            max(1, int(rendered.width * self.display_scale)),
            max(1, int(rendered.height * self.display_scale)),
        )
        display = rendered.resize(display_size, Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(display)
        ox = (self.canvas.winfo_width() - display_size[0]) / 2
        oy = (self.canvas.winfo_height() - display_size[1]) / 2
        self.display_origin = (ox, oy)
        self.canvas.create_image(ox, oy, image=self.preview_photo, anchor="nw")

        for index, region in enumerate(doc.regions, 1):
            x1 = ox + region.x * self.display_scale
            y1 = oy + region.y * self.display_scale
            x2 = ox + region.x2 * self.display_scale
            y2 = oy + region.y2 * self.display_scale
            color = MODE_COLORS[region.mode]
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2)
            self.canvas.create_text(
                x1 + 4,
                y1 + 4,
                text=f"{index} {MODE_LABELS[region.mode]}",
                fill="white",
                anchor="nw",
                font=("Malgun Gothic", 9, "bold"),
            )

    def save_next_to_sources(self) -> None:
        if not self.documents:
            return
        self._save_documents(None)

    def save_to_folder(self) -> None:
        if not self.documents:
            return
        output = filedialog.askdirectory(title="결과를 저장할 폴더")
        if not output:
            return
        self._save_documents(Path(output))

    def _save_documents(self, selected_output_dir: Path | None) -> None:
        saved = 0
        saved_paths: list[Path] = []
        reserved_paths: set[Path] = set()
        try:
            for doc in self.documents:
                stem = doc.path.stem
                output_dir = selected_output_dir or doc.path.parent
                output_dir.mkdir(parents=True, exist_ok=True)
                grid_path = output_dir / f"{stem}_얼굴격자.png"
                duplicate_number = 2
                while grid_path in reserved_paths:
                    grid_path = output_dir / f"{stem}_얼굴격자_{duplicate_number}.png"
                    duplicate_number += 1
                reserved_paths.add(grid_path)
                rendered = render_regions(
                    doc.image,
                    doc.regions,
                    color=self.grid_color,
                    opacity=int(round(self.opacity.get())),
                    spacing_percent=self.spacing.get(),
                    thickness_percent=self.thickness.get(),
                    margin_percent=self.margin.get(),
                )
                metadata = {
                    "source": str(doc.path),
                    "output": str(grid_path),
                    "settings": {
                        "color": self.grid_color,
                        "opacity": int(round(self.opacity.get())),
                        "spacing_percent": self.spacing.get(),
                        "thickness_percent": self.thickness.get(),
                        "margin_percent": self.margin.get(),
                    },
                    "regions": [region.to_dict() for region in doc.regions],
                }
                png_metadata = PngInfo()
                png_metadata.add_text("FaceGridStamper", json.dumps(metadata, ensure_ascii=False))
                rendered.save(grid_path, pnginfo=png_metadata)
                saved += 1
                saved_paths.append(grid_path)
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror(APP_TITLE, f"저장 중 오류가 발생했습니다.\n{exc}")
            return
        if saved == 1:
            self.status.set(f"저장했습니다: {saved_paths[0]}")
        elif selected_output_dir:
            self.status.set(f"{saved}개 이미지를 저장했습니다: {selected_output_dir}")
        else:
            self.status.set(f"{saved}개 이미지를 각 원본 옆에 저장했습니다.")


def main() -> None:
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except tk.TclError:
        pass
    FaceGridApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
