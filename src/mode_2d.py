import napari
import numpy as np
from magicgui.widgets import Container, Label, PushButton, CheckBox, IntSlider

# 色定数
COLOR_AXIAL = 'blue'
COLOR_CORONAL = 'green'
COLOR_SAGITTAL = 'red'

class Slice2DController:
    def __init__(self, viewer: napari.Viewer):
        self.viewer = viewer
        self.data = None
        self._block_events = False # 無限ループ防止用フラグ
        
        # --- UI Components ---
        self.btn_axial = PushButton(text="Axial (Z)")
        self.btn_coronal = PushButton(text="Coronal (Y)")
        self.btn_sagittal = PushButton(text="Sagittal (X)")
        
        self.btn_axial.native.setStyleSheet(f"color: {COLOR_AXIAL}; font-weight: bold;")
        self.btn_coronal.native.setStyleSheet(f"color: {COLOR_CORONAL}; font-weight: bold;")
        self.btn_sagittal.native.setStyleSheet(f"color: {COLOR_SAGITTAL}; font-weight: bold;")

        self.btn_axial.clicked.connect(lambda: self._set_axis(0))
        self.btn_coronal.clicked.connect(lambda: self._set_axis(1))
        self.btn_sagittal.clicked.connect(lambda: self._set_axis(2))

        # スライス移動スライダ
        self.slider_slice = IntSlider(label="Slice Index")
        self.slider_slice.changed.connect(self._on_slider_change)
        
        self.row_slider, self.lbl_slice_text = self._create_slider_row(self.slider_slice)

        self.chk_crosshair = CheckBox(value=True, label="Show Crosshairs")
        self.chk_crosshair.changed.connect(self._update_crosshairs)

        self.widget = Container(
            widgets=[
                Label(value="--- 2D Controls ---"),
                Container(widgets=[self.btn_axial, self.btn_sagittal, self.btn_coronal], layout="horizontal", labels=False),
                self.row_slider,
                self.chk_crosshair
            ],
            visible=False
        )

        # Napari側のスライス変更イベント
        self.viewer.dims.events.current_step.connect(self._on_dims_change)

    def _create_slider_row(self, slider):
        lbl = Label(value=slider.label) # ラベル作成
        lbl.min_width = 100
        
        btn = PushButton(text="R")
        btn.max_width = 40
        def reset_slice():
            if slider.max > 0:
                slider.value = slider.max // 2
        btn.clicked.connect(reset_slice)
        
        container = Container(widgets=[lbl, slider, btn], layout="horizontal", labels=False)
        return container, lbl # ラベルオブジェクトも返す

    def set_data(self, data):
        self.data = data
        if self.widget.visible:
            self._update_slider_range()

    def activate(self):
        self.widget.visible = True
        self.viewer.dims.ndisplay = 2
        self._setup_layers()
        # 有効化した直後に範囲を同期させる
        self._update_slider_range()

    def deactivate(self):
        self.widget.visible = False

    def _setup_layers(self):
        if not self.data: return
        
        # 画像と同じスケール定義を取得
        scale = [self.data.slice_thickness, self.data.pixel_spacing[0], self.data.pixel_spacing[1]]
        
        # 画像レイヤー
        self.viewer.add_image(
            self.data.volume, name="DICOM Series",
            scale=scale,
            colormap="gray", blending="translucent"
        )
        
        # Shapesレイヤーにも同じscaleを渡す
        self.viewer.add_shapes(
            name="Crosshairs", 
            edge_width=2, 
            face_color=[0,0,0,0], 
            ndim=3,
            scale=scale 
        )
        
        self._set_axis(0)

    def _set_axis(self, axis_idx):
        if not self.widget.visible or not self.data: return
        self._block_events = True
        
        order_map = {0: (0, 1, 2), 1: (1, 0, 2), 2: (2, 0, 1)}
        label_map = {0: "Axial Slice", 1: "Coronal Slice", 2: "Sagittal Slice"}
        
        self.viewer.dims.order = order_map[axis_idx]
        self.viewer.reset_view()
        
        # ラベルとスライダの更新
        new_label = label_map[axis_idx]
        self.slider_slice.label = new_label
        self.lbl_slice_text.value = new_label

        # 新しい軸の長さを取得してスライダの最大値を更新
        current_axis = self.viewer.dims.order[0]
        max_idx = self.data.volume.shape[current_axis] - 1
        self.slider_slice.max = max_idx
        
        # 現在の位置にスライダを合わせる
        current_pos = self.viewer.dims.current_step[current_axis]
        if current_pos > max_idx: current_pos = max_idx
        self.slider_slice.value = current_pos
        
        self._update_crosshairs()
        self._block_events = False

    def _update_slider_range(self):
        """現在の視点軸に合わせてスライダの最大値を更新（安全版）"""
        if not self.data: return
        self._block_events = True
        
        current_axis = self.viewer.dims.order[0]
        max_idx = self.data.volume.shape[current_axis] - 1
        
        if self.slider_slice.value > max_idx:
            self.slider_slice.value = max_idx
            self.slider_slice.max = max_idx
        else:
            self.slider_slice.max = max_idx
            self.slider_slice.value = self.viewer.dims.current_step[current_axis]

        self._block_events = False

    def _on_slider_change(self, event=None):
        """UIスライダ -> Napari"""
        if self._block_events or not self.widget.visible: return
        
        current_axis = self.viewer.dims.order[0]
        current_step = list(self.viewer.dims.current_step)
        
        # Napariに値を送る
        current_step[current_axis] = self.slider_slice.value
        self.viewer.dims.current_step = tuple(current_step)

    def _on_dims_change(self, event):
        """Napari -> UIスライダ"""
        if not self.widget.visible: return
        
        current_axis = self.viewer.dims.order[0]
        val = self.viewer.dims.current_step[current_axis]
        
        # ★修正ポイント: 値が変わっていなくても、クロスヘア更新のために処理を継続させる
        # ただし、無限ループ防止のためスライダへの書き込みだけをガードする
        if self.slider_slice.value != val:
            self._block_events = True
            try:
                if val > self.slider_slice.max:
                    self.slider_slice.max = val
                self.slider_slice.value = val
            except ValueError:
                pass
            finally:
                self._block_events = False
            
        # ★ここが重要: スライダ更新の有無に関わらず、クロスヘアは必ず再描画する
        self._update_crosshairs()

    def _update_crosshairs(self):
        if not self.data or "Crosshairs" not in self.viewer.layers: return
        layer = self.viewer.layers["Crosshairs"]
        layer.data = []
        
        if not self.chk_crosshair.value: return

        current_step = self.viewer.dims.current_step
        order = self.viewer.dims.order
        z, y, x = self.data.volume.shape
        
        # int() でキャストして整数にする
        cz, cy, cx = int(current_step[0]), int(current_step[1]), int(current_step[2])
        
        # 座標が範囲外の場合のガード
        cz = min(cz, z-1)
        cy = min(cy, y-1)
        cx = min(cx, x-1)

        shapes, colors = [], []
        if order[0] == 0: # Axial
            shapes.append([[cz, 0, 0], [cz, y, 0], [cz, y, x], [cz, 0, x], [cz, 0, 0]])
            colors.append(COLOR_AXIAL)
            shapes.append([[cz, 0, cx], [cz, y, cx]])
            colors.append(COLOR_SAGITTAL)
            shapes.append([[cz, cy, 0], [cz, cy, x]])
            colors.append(COLOR_CORONAL)
        elif order[0] == 1: # Coronal
            shapes.append([[0, cy, 0], [z, cy, 0], [z, cy, x], [0, cy, x], [0, cy, 0]])
            colors.append(COLOR_CORONAL)
            shapes.append([[0, cy, cx], [z, cy, cx]])
            colors.append(COLOR_SAGITTAL)
            shapes.append([[cz, cy, 0], [cz, cy, x]])
            colors.append(COLOR_AXIAL)
        elif order[0] == 2: # Sagittal
            shapes.append([[0, 0, cx], [z, 0, cx], [z, y, cx], [0, y, cx], [0, 0, cx]])
            colors.append(COLOR_SAGITTAL)
            shapes.append([[0, cy, cx], [z, cy, cx]])
            colors.append(COLOR_CORONAL)
            shapes.append([[cz, 0, cx], [cz, y, cx]])
            colors.append(COLOR_AXIAL)

        if len(shapes) > 0:
            layer.add(shapes, shape_type='path', edge_color=colors)