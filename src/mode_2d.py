import napari
import numpy as np
from magicgui.widgets import Container, Label, PushButton, CheckBox, IntSlider

# 色定数
COLOR_AXIAL = 'blue'
COLOR_CORONAL = 'green'
COLOR_SAGITTAL = 'red'
COLOR_TEXT = 'yellow' # ラベルの色

class Slice2DController:
    def __init__(self, viewer: napari.Viewer):
        self.viewer = viewer
        self.data = None
        
        # 現在のスライス位置 [z, y, x]
        self.current_pos = [0, 0, 0]
        # 現在メインで表示している軸 (0:Axial, 1:Coronal, 2:Sagittal)
        self.main_axis = 0 
        
        # --- UI Components ---
        self.btn_axial = PushButton(text="Main: Axial (Z)")
        self.btn_coronal = PushButton(text="Main: Coronal (Y)")
        self.btn_sagittal = PushButton(text="Main: Sagittal (X)")
        
        self.btn_axial.native.setStyleSheet(f"color: {COLOR_AXIAL}; font-weight: bold;")
        self.btn_coronal.native.setStyleSheet(f"color: {COLOR_CORONAL}; font-weight: bold;")
        self.btn_sagittal.native.setStyleSheet(f"color: {COLOR_SAGITTAL}; font-weight: bold;")

        self.btn_axial.clicked.connect(lambda: self._set_main_axis(0))
        self.btn_coronal.clicked.connect(lambda: self._set_main_axis(1))
        self.btn_sagittal.clicked.connect(lambda: self._set_main_axis(2))

        # スライス移動スライダ
        self.slider_slice = IntSlider(label="Slice Index")
        self.slider_slice.changed.connect(self._on_slider_change)
        
        self.row_slider, self.lbl_slice_text = self._create_slider_row(self.slider_slice)

        self.chk_crosshair = CheckBox(value=True, label="Show Crosshairs")
        self.chk_crosshair.changed.connect(self._update_crosshairs)

        self.widget = Container(
            widgets=[
                Label(value="--- 2D Multi-View ---"),
                Container(widgets=[self.btn_axial, self.btn_sagittal, self.btn_coronal], layout="vertical", labels=False),
                self.row_slider,
                self.chk_crosshair
            ],
            visible=False
        )

    def _create_slider_row(self, slider):
        lbl = Label(value=slider.label)
        lbl.min_width = 100
        btn = PushButton(text="R")
        btn.max_width = 40
        def reset_slice():
            if slider.max > 0:
                slider.value = slider.max // 2
        btn.clicked.connect(reset_slice)
        container = Container(widgets=[lbl, slider, btn], layout="horizontal", labels=False)
        return container, lbl

    def set_data(self, data):
        self.data = data
        if self.data:
            z, y, x = data.volume.shape
            self.current_pos = [z//2, y//2, x//2]

        if self.widget.visible:
            self._update_slider_range()
            self._refresh_all()

    def activate(self):
        self.widget.visible = True
        self.viewer.dims.ndisplay = 2
        self._setup_layers()
        self._set_main_axis(0) 

    def deactivate(self):
        self.widget.visible = False

    def _setup_layers(self):
        if not self.data: return
        self.viewer.layers.clear()
        
        sp_z = self.data.slice_thickness
        sp_y = self.data.pixel_spacing[0]
        sp_x = self.data.pixel_spacing[1]

        # 3つのImageレイヤー
        self.viewer.add_image(
            np.zeros((10, 10)), name="View Axial", colormap="gray", blending="translucent",
            scale=[sp_y, sp_x]
        )
        self.viewer.add_image(
            np.zeros((10, 10)), name="View Coronal", colormap="gray", blending="translucent",
            scale=[sp_z, sp_x]
        )
        self.viewer.add_image(
            np.zeros((10, 10)), name="View Sagittal", colormap="gray", blending="translucent",
            scale=[sp_z, sp_y]
        )

        # クロスヘアレイヤー
        self.viewer.add_shapes(name="Crosshair Axial", edge_width=2, face_color=[0,0,0,0], ndim=2)
        self.viewer.add_shapes(name="Crosshair Coronal", edge_width=2, face_color=[0,0,0,0], ndim=2)
        self.viewer.add_shapes(name="Crosshair Sagittal", edge_width=2, face_color=[0,0,0,0], ndim=2)

        # ★修正: properties={'label': []} を追加
        # これにより、初期化時点から "label" というキーが存在することをNapariに伝えます
        self.viewer.add_points(
            name="View Labels",
            size=0,
            properties={'label': []}, # <--- ここが修正ポイントです
            text={
                'string': '{label}',
                'color': COLOR_TEXT,
                'size': 12,
                'anchor': 'upper_left',
                'translation': [5, 5]
            }
        )

        self._refresh_all()

    def _set_main_axis(self, axis_idx):
        self.main_axis = axis_idx
        
        label_map = {0: "Main: Axial (Z)", 1: "Main: Coronal (Y)", 2: "Main: Sagittal (X)"}
        self.slider_slice.label = label_map[axis_idx]
        self.lbl_slice_text.value = label_map[axis_idx]

        self._update_slider_range()
        self._update_layout() 
        self._refresh_all()
        self.viewer.reset_view()

    def _update_slider_range(self):
        if not self.data: return
        max_idx = self.data.volume.shape[self.main_axis] - 1
        self.slider_slice.max = max_idx
        self.slider_slice.value = self.current_pos[self.main_axis]

    def _on_slider_change(self, event=None):
        if not self.data: return
        val = self.slider_slice.value
        self.current_pos[self.main_axis] = val
        self._refresh_all()

    def _refresh_all(self):
        self._update_images()
        self._update_crosshairs()

    def _update_images(self):
        if not self.data: return
        
        z, y, x = self.current_pos
        vol = self.data.volume

        z = np.clip(z, 0, vol.shape[0]-1)
        y = np.clip(y, 0, vol.shape[1]-1)
        x = np.clip(x, 0, vol.shape[2]-1)
        
        if "View Axial" in self.viewer.layers:
            self.viewer.layers["View Axial"].data = vol[z, :, :]
        if "View Coronal" in self.viewer.layers:
            self.viewer.layers["View Coronal"].data = vol[:, y, :]
        if "View Sagittal" in self.viewer.layers:
            self.viewer.layers["View Sagittal"].data = vol[:, :, x]

    def _update_layout(self):
        if not self.data: return
        
        layers = ["View Axial", "View Coronal", "View Sagittal"]
        shapes = ["Crosshair Axial", "Crosshair Coronal", "Crosshair Sagittal"]
        
        if not all(l in self.viewer.layers for l in layers): return
        
        l_objs = [self.viewer.layers[l] for l in layers]
        s_objs = [self.viewer.layers[s] for s in shapes]
        
        shape = self.data.volume.shape
        sp = [self.data.slice_thickness, self.data.pixel_spacing[0], self.data.pixel_spacing[1]]
        
        base_scales = [[sp[1], sp[2]], [sp[0], sp[2]], [sp[0], sp[1]]]
        size_z = shape[0] * sp[0]
        size_y = shape[1] * sp[1]
        size_x = shape[2] * sp[2]
        
        view_dims = [(size_y, size_x), (size_z, size_x), (size_z, size_y)]
        
        main_idx = self.main_axis
        sub_indices = [i for i in [0, 1, 2] if i != main_idx]
        
        # --- レイアウト計算と適用 ---
        
        # 1. Main View
        l_objs[main_idx].scale = base_scales[main_idx]
        l_objs[main_idx].translate = [0, 0]
        l_objs[main_idx].opacity = 1.0
        s_objs[main_idx].scale = base_scales[main_idx]
        s_objs[main_idx].translate = [0, 0]
        
        # ラベル用座標保存リスト: (label_text, [y, x])
        labels_data = []
        labels_data.append(("Axial" if main_idx==0 else "Coronal" if main_idx==1 else "Sagittal", [0, 0]))

        main_h, main_w = view_dims[main_idx]
        offset_x = main_w + (main_w * 0.05)
        scale_factor = 0.4
        current_y = 0
        
        # 2. Sub Views
        for sub_i in sub_indices:
            new_scale = [s * scale_factor for s in base_scales[sub_i]]
            pos = [current_y, offset_x]
            
            l_objs[sub_i].scale = new_scale
            s_objs[sub_i].scale = new_scale
            l_objs[sub_i].translate = pos
            s_objs[sub_i].translate = pos
            l_objs[sub_i].opacity = 1.0
            
            label_text = "Axial" if sub_i==0 else "Coronal" if sub_i==1 else "Sagittal"
            labels_data.append((label_text, pos))
            
            sub_h = view_dims[sub_i][0] * scale_factor
            current_y += sub_h + (main_h * 0.05)

        # ラベルの更新
        self._update_labels(labels_data)

    def _update_labels(self, labels_data):
        """View Labelsレイヤーを更新"""
        if "View Labels" not in self.viewer.layers: return
        
        points = []
        properties = {'label': []}
        
        for text, coord in labels_data:
            points.append(coord)
            properties['label'].append(text)
            
        layer = self.viewer.layers["View Labels"]
        layer.data = np.array(points)
        layer.properties = properties
        layer.refresh()

    def _update_crosshairs(self):
        if not self.data: return

        for name in ["Crosshair Axial", "Crosshair Coronal", "Crosshair Sagittal"]:
            if name in self.viewer.layers:
                self.viewer.layers[name].data = []

        if not self.chk_crosshair.value: return

        z, y, x = self.current_pos
        vol_sh = self.data.volume.shape
        
        if "Crosshair Axial" in self.viewer.layers:
            layer = self.viewer.layers["Crosshair Axial"]
            lines = [[[0, x], [vol_sh[1], x]], [[y, 0], [y, vol_sh[2]]]]
            colors = [COLOR_SAGITTAL, COLOR_CORONAL]
            layer.add(lines, shape_type='path', edge_color=colors, edge_width=2)

        if "Crosshair Coronal" in self.viewer.layers:
            layer = self.viewer.layers["Crosshair Coronal"]
            lines = [[[0, x], [vol_sh[0], x]], [[z, 0], [z, vol_sh[2]]]]
            colors = [COLOR_SAGITTAL, COLOR_AXIAL]
            layer.add(lines, shape_type='path', edge_color=colors, edge_width=2)
            
        if "Crosshair Sagittal" in self.viewer.layers:
            layer = self.viewer.layers["Crosshair Sagittal"]
            lines = [[[0, y], [vol_sh[0], y]], [[z, 0], [z, vol_sh[1]]]]
            colors = [COLOR_CORONAL, COLOR_AXIAL]
            layer.add(lines, shape_type='path', edge_color=colors, edge_width=2)
