import napari
from pathlib import Path # パス操作用にインポートを追加
from magicgui.widgets import Container, Label, PushButton, SpinBox, Table, ComboBox, FloatSlider # FloatSliderを追加

from dicom_loader import load_dicom_series, DicomSeriesData
from mode_2d import Slice2DController
from mode_ortho import Ortho3DController
from mode_volume import Volume3DController

class DicomViewerApp:
    def __init__(self):
        # 修正1: 初期タイトルを "DICOM Viewer" に変更
        self.viewer = napari.Viewer(title="DICOM Viewer")
        self.current_data: DicomSeriesData | None = None
        
        # モード管理
        self.modes = {
            "2D Slice Mode": Slice2DController(self.viewer),
            "3D Orthogonal Mode": Ortho3DController(self.viewer),
            "3D Volume Mode": Volume3DController(self.viewer)
        }
        self.current_mode_name = "2D Slice Mode"

        # --- Left Sidebar (DICOM Info) ---
        self.lbl_summary = Label(value="No Data")
        self.tbl_header = Table(value=[], label="All DICOM Tags")
        
        self.left_container = Container(
            widgets=[
                Label(value="--- Basic Info ---"),
                self.lbl_summary,
                Label(value="--- Header Details ---"),
                self.tbl_header
            ],
            labels=False 
        )
        self.viewer.window.add_dock_widget(self.left_container, area="left", name="DICOM Info")

        # --- Right Sidebar (Control Panel) ---
        self._init_main_controls()

    def _init_main_controls(self):
        self.btn_load = PushButton(text="Open DICOM Folder")
        self.btn_load.clicked.connect(self._open_folder)
        
        self.lbl_status = Label(value="Ready") 

        self.combo_mode = ComboBox(
            choices=list(self.modes.keys()),
            label="View Mode",
            value=self.current_mode_name
        )
        self.combo_mode.changed.connect(self._on_mode_change)

        # --- Windowing Controls (Sliderに変更) ---
        # SpinBox -> FloatSlider に変更
        self.slider_wc = FloatSlider(value=40, min=-2000, max=8000, step=1, label="W Level")
        self.slider_ww = FloatSlider(value=400, min=1, max=8000, step=1, label="W Width")
        
        self.slider_wc.changed.connect(self._update_contrast)
        self.slider_ww.changed.connect(self._update_contrast)

        # リセット行の作成
        row_wc = self._create_reset_row(self.slider_wc, self._reset_wc)
        row_ww = self._create_reset_row(self.slider_ww, self._reset_ww)

        widgets_list = [
            self.btn_load,
            self.lbl_status,
            Label(value="----------------"),
            self.combo_mode,
        ]
        
        for mode in self.modes.values():
            widgets_list.append(mode.widget)

        widgets_list.extend([
            Label(value="--- Windowing ---"),
            row_wc,
            row_ww
        ])

        self.container = Container(widgets=widgets_list)
        self.viewer.window.add_dock_widget(self.container, area="right", name="Controls")

        self.modes[self.current_mode_name].activate()

    def _create_reset_row(self, widget, reset_func):
        lbl = Label(value=widget.label)
        lbl.min_width = 100
        btn = PushButton(text="R")
        btn.max_width = 40
        btn.clicked.connect(reset_func)
        return Container(widgets=[lbl, widget, btn], layout="horizontal", labels=False)

    def _reset_wc(self):
        if self.current_data:
            self.slider_wc.value = float(self.current_data.window_center)

    def _reset_ww(self):
        if self.current_data:
            self.slider_ww.value = float(self.current_data.window_width)

    def _open_folder(self):
        from qtpy.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(None, "Select DICOM Folder")
        if folder:
            try:
                data = load_dicom_series(folder)
                self.current_data = data
                
                # --- ウィンドウタイトルの更新 ---
                folder_path = Path(folder)
                folder_name = folder_path.name   # フォルダ名
                series_name = data.series_description # DICOMヘッダの系列名
                
                # 修正2: タイトルを変更
                self.viewer.title = f"{folder_name} - {series_name}"

                # --- 左サイドバーの更新 ---
                z, y, x = data.volume.shape
                summary_text = (
                    f"Size: {x} x {y}\n"
                    f"Thickness: {data.slice_thickness} mm\n"
                    f"Count: {z} slices"
                )
                self.lbl_summary.value = summary_text
                self.tbl_header.value = data.header_data
                
                # --- 右サイドバー等の更新 ---
                self.lbl_status.value = "Loaded"
                
                self._reset_wc()
                self._reset_ww()

                for mode in self.modes.values():
                    mode.set_data(data)

                self._refresh_view()

            except Exception as e:
                self.lbl_status.value = f"Error: {e}"
                import traceback
                traceback.print_exc()

    def _on_mode_change(self, event=None):
        self.modes[self.current_mode_name].deactivate()
        self.current_mode_name = self.combo_mode.value
        self.viewer.layers.clear()
        self.modes[self.current_mode_name].activate()
        self._update_contrast()

    def _refresh_view(self):
        self.viewer.layers.clear()
        self.modes[self.current_mode_name].activate()
        self._update_contrast()

    def _update_contrast(self):
        wc = self.slider_wc.value
        ww = self.slider_ww.value
        lower = wc - (ww / 2)
        upper = wc + (ww / 2)
        for layer in self.viewer.layers:
            if isinstance(layer, napari.layers.Image):
                layer.contrast_limits = (lower, upper)

def run():
    app = DicomViewerApp()
    napari.run()