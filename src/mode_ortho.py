import napari
import numpy as np
from magicgui.widgets import Container, Label, IntSlider, CheckBox, PushButton

# 色定数
COLOR_AXIAL = 'blue'
COLOR_CORONAL = 'green'
COLOR_SAGITTAL = 'red'

class Ortho3DController:
    def __init__(self, viewer: napari.Viewer):
        self.viewer = viewer
        self.data = None
        
        # --- UI Components ---
        self.slider_z = IntSlider(label="Axial")
        self.slider_y = IntSlider(label="Coronal")
        self.slider_x = IntSlider(label="Sagittal")
        
        self.slider_z.changed.connect(self._update_planes)
        self.slider_y.changed.connect(self._update_planes)
        self.slider_x.changed.connect(self._update_planes)

        row_z = self._create_slider_row(self.slider_z, self._reset_z)
        row_y = self._create_slider_row(self.slider_y, self._reset_y)
        row_x = self._create_slider_row(self.slider_x, self._reset_x)

        self.chk_3d_vol = CheckBox(value=False, label="Show 3D Volume")
        self.chk_3d_vol.changed.connect(self._update_visibility)

        self.widget = Container(
            widgets=[
                Label(value="--- Ortho Controls ---"),
                row_z, row_y, row_x,
                self.chk_3d_vol
            ],
            visible=False
        )

    def _create_slider_row(self, slider, reset_func):
        # 1. ラベルウィジェットを作成 (幅を固定して揃えるときれい)
        lbl = Label(value=slider.label)
        lbl.min_width = 100 

        # 2. リセットボタン
        btn = PushButton(text="R")
        btn.max_width = 40
        btn.clicked.connect(reset_func)
        
        # 3. [ラベル] [スライダ] [ボタン] の順で並べる
        return Container(widgets=[lbl, slider, btn], layout="horizontal", labels=False)

    def _reset_z(self):
        if self.slider_z.max > 0: self.slider_z.value = self.slider_z.max // 2
    def _reset_y(self):
        if self.slider_y.max > 0: self.slider_y.value = self.slider_y.max // 2
    def _reset_x(self):
        if self.slider_x.max > 0: self.slider_x.value = self.slider_x.max // 2

    def set_data(self, data):
        self.data = data
        z, y, x = data.volume.shape
        self.slider_z.max = z - 1
        self.slider_y.max = y - 1
        self.slider_x.max = x - 1
        self._reset_z()
        self._reset_y()
        self._reset_x()

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
        
        # 平面表示の設定
        # depiction='plane' を使うとGPUで断面計算を行うため高速です
        params = {
            "scale": scale, 
            "colormap": "gray", 
            "blending": "translucent_no_depth", 
            "depiction": "plane", 
            "rendering": "mip"
        }
        
        self.viewer.add_image(self.data.volume, name="Axial Plane", plane={"normal": (1,0,0)}, **params)
        self.viewer.add_image(self.data.volume, name="Coronal Plane", plane={"normal": (0,1,0)}, **params)
        self.viewer.add_image(self.data.volume, name="Sagittal Plane", plane={"normal": (0,0,1)}, **params)
        
        # 3D Volume (全体像)
        self.viewer.add_image(
            self.data.volume, name="3D Volume", scale=scale, 
            colormap="gray", blending="additive", rendering="mip", 
            visible=self.chk_3d_vol.value
        )

        # ★追加: 枠線用のShapesレイヤー
        # ここにも scale を渡すのが重要です！
        self.viewer.add_shapes(
            name="Ortho Frames",
            edge_width=3,          # 線の太さ
            face_color=[0,0,0,0],  # 塗りつぶしなし（透明）
            ndim=3,
            scale=scale            # 画像と同じスケールを適用
        )

        self._update_planes()

    def _update_planes(self, event=None):
        if not self.widget.visible or not self.data: return
        
        z_idx = self.slider_z.value
        y_idx = self.slider_y.value
        x_idx = self.slider_x.value

        # 1. 画像平面の位置更新
        if "Axial Plane" in self.viewer.layers:
            self.viewer.layers["Axial Plane"].plane.position = (z_idx, 0, 0)
            self.viewer.layers["Coronal Plane"].plane.position = (0, y_idx, 0)
            self.viewer.layers["Sagittal Plane"].plane.position = (0, 0, x_idx)

        # 2. 枠線の更新
        if "Ortho Frames" in self.viewer.layers:
            layer = self.viewer.layers["Ortho Frames"]
            layer.data = [] # 一旦クリア

            z_dim, y_dim, x_dim = self.data.volume.shape
            
            shapes = []
            colors = []

            # Axial枠 (青): z=z_idx で固定、XY平面の長方形
            rect_axial = [
                [z_idx, 0, 0], 
                [z_idx, y_dim, 0], 
                [z_idx, y_dim, x_dim], 
                [z_idx, 0, x_dim],
                [z_idx, 0, 0] # 閉じる
            ]
            shapes.append(rect_axial)
            colors.append(COLOR_AXIAL)

            # Coronal枠 (緑): y=y_idx で固定、XZ平面の長方形
            rect_coronal = [
                [0, y_idx, 0],
                [z_dim, y_idx, 0],
                [z_dim, y_idx, x_dim],
                [0, y_idx, x_dim],
                [0, y_idx, 0] # 閉じる
            ]
            shapes.append(rect_coronal)
            colors.append(COLOR_CORONAL)

            # Sagittal枠 (赤): x=x_idx で固定、YZ平面の長方形
            rect_sagittal = [
                [0, 0, x_idx],
                [z_dim, 0, x_idx],
                [z_dim, y_dim, x_idx],
                [0, y_dim, x_idx],
                [0, 0, x_idx] # 閉じる
            ]
            shapes.append(rect_sagittal)
            colors.append(COLOR_SAGITTAL)

            # まとめて描画
            layer.add(shapes, shape_type='path', edge_color=colors)

    def _update_visibility(self):
        if "3D Volume" in self.viewer.layers:
            self.viewer.layers["3D Volume"].visible = self.chk_3d_vol.value