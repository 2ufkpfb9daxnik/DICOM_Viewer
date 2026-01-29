import napari
import numpy as np
from magicgui.widgets import Container, Label, PushButton, FloatSlider, RangeSlider

class Volume3DController:
    def __init__(self, viewer: napari.Viewer):
        self.viewer = viewer
        self.data = None
        
        # --- Transform Sliders ---
        self.slider_tx = FloatSlider(min=-200, max=200, label="Pos X")
        self.slider_ty = FloatSlider(min=-200, max=200, label="Pos Y")
        self.slider_tz = FloatSlider(min=-200, max=200, label="Pos Z")
        self.slider_roll = FloatSlider(min=-180, max=180, label="Roll (Z)")
        self.slider_pitch = FloatSlider(min=-180, max=180, label="Pitch (Y)")
        self.slider_yaw = FloatSlider(min=-180, max=180, label="Yaw (X)")
        
        # --- Clipping Sliders ---
        self.range_z = RangeSlider(label="Clip Z")
        self.range_y = RangeSlider(label="Clip Y")
        self.range_x = RangeSlider(label="Clip X")

        # イベント接続
        transform_sliders = [self.slider_tx, self.slider_ty, self.slider_tz, 
                             self.slider_roll, self.slider_pitch, self.slider_yaw]
        for w in transform_sliders:
            w.changed.connect(self._update_transform)

        for w in [self.range_z, self.range_y, self.range_x]:
            w.changed.connect(self._update_clipping)

        # --- UI Layout (With Reset Buttons) ---
        widgets = [Label(value="--- Transform ---")]
        
        # Transform用の行作成 (リセット先はすべて0)
        for s in transform_sliders:
            widgets.append(self._create_row(s, 0.0))
            
        widgets.append(Label(value="--- Clipping ---"))
        
        # Clipping用の行作成 (リセット先は動的だが、ここではボタンだけ配置)
        # ラムダ式で遅延評価させないと、全て最後のスライダを参照してしまうため注意が必要
        # ここではシンプルに専用のメソッドに飛ばします
        widgets.append(self._create_clip_row(self.range_z))
        widgets.append(self._create_clip_row(self.range_y))
        widgets.append(self._create_clip_row(self.range_x))

        self.widget = Container(widgets=widgets, visible=False)

    def _create_row(self, slider, reset_val):
        """通常スライダ用の行作成"""
        # ラベル追加
        lbl = Label(value=slider.label)
        lbl.min_width = 100
        
        btn = PushButton(text="R")
        btn.max_width = 40
        btn.clicked.connect(lambda: setattr(slider, 'value', reset_val))
        
        return Container(widgets=[lbl, slider, btn], layout="horizontal", labels=False)

    def _create_clip_row(self, slider):
        """RangeSlider用の行作成"""
        # ラベル追加
        lbl = Label(value=slider.label)
        lbl.min_width = 100
        
        btn = PushButton(text="R")
        btn.max_width = 40
        def reset_range():
            slider.value = (slider.min, slider.max)
        btn.clicked.connect(reset_range)
        
        return Container(widgets=[lbl, slider, btn], layout="horizontal", labels=False)

    def set_data(self, data):
        self.data = data
        z, y, x = data.volume.shape
        
        # 範囲設定
        self.range_z.min, self.range_z.max = 0, z
        self.range_y.min, self.range_y.max = 0, y
        self.range_x.min, self.range_x.max = 0, x
        
        # 値リセット
        self.range_z.value = (0, z)
        self.range_y.value = (0, y)
        self.range_x.value = (0, x)

    def activate(self):
        self.widget.visible = True
        self.viewer.dims.ndisplay = 3
        self.viewer.camera.angles = (135, -45, 135)
        self._setup_layers()

    def deactivate(self):
        self.widget.visible = False

    def _setup_layers(self):
        if not self.data: return
        scale = [self.data.slice_thickness, self.data.pixel_spacing[0], self.data.pixel_spacing[1]]
        self.viewer.add_image(
            self.data.volume, name="Voxel Volume", scale=scale, colormap="gray",
            blending="additive", rendering="mip", interpolation3d="linear"
        )
        # Transformリセット
        self.slider_tx.value = self.slider_ty.value = self.slider_tz.value = 0
        self.slider_roll.value = self.slider_pitch.value = self.slider_yaw.value = 0
        self._update_clipping()

    def _update_transform(self, event=None):
        if "Voxel Volume" not in self.viewer.layers: return
        roll, pitch, yaw = np.radians(self.slider_roll.value), np.radians(self.slider_pitch.value), np.radians(self.slider_yaw.value)
        c, s = np.cos(roll), np.sin(roll)
        Rz = np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]])
        c, s = np.cos(pitch), np.sin(pitch)
        Ry = np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])
        c, s = np.cos(yaw), np.sin(yaw)
        Rx = np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        
        T = np.eye(4)
        T[0:3, 3] = [self.slider_tz.value, self.slider_ty.value, self.slider_tx.value]
        self.viewer.layers["Voxel Volume"].affine = T @ Rz @ Ry @ Rx

    def _update_clipping(self, event=None):
        if "Voxel Volume" not in self.viewer.layers: return
        z_min, z_max = self.range_z.value
        y_min, y_max = self.range_y.value
        x_min, x_max = self.range_x.value
        planes = [
            {"position": (z_min, 0, 0), "normal": (1, 0, 0)}, {"position": (z_max, 0, 0), "normal": (-1, 0, 0)},
            {"position": (0, y_min, 0), "normal": (0, 1, 0)}, {"position": (0, y_max, 0), "normal": (0, -1, 0)},
            {"position": (0, 0, x_min), "normal": (0, 0, 1)}, {"position": (0, 0, x_max), "normal": (0, 0, -1)}
        ]
        self.viewer.layers["Voxel Volume"].experimental_clipping_planes = planes