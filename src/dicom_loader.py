import os
import pydicom
import numpy as np
from pathlib import Path
from dataclasses import dataclass

@dataclass
class DicomSeriesData:
    volume: np.ndarray
    pixel_spacing: list[float]
    slice_thickness: float
    series_description: str
    # 変更: header_summary(str) の代わりに header_data(list) を持ちます
    header_data: list[dict] 
    window_center: float
    window_width: float

def format_dicom_header(dcm: pydicom.dataset.FileDataset) -> list[dict]:
    """
    DICOMデータセットから主要なタグを抽出し、
    UIのテーブルで表示しやすい辞書のリスト形式に正規化する純粋関数
    """
    header_rows = []
    
    # 階層を持たずフラットに全タグを走査
    for elem in dcm:
        # Pixel DataやOverlay Dataなど、巨大なバイナリデータは表示から除外
        if elem.tag.group in (0x7FE0, 0x6000, 0x6002):
            continue
        
        # 値の整形（長い文字列は切り詰めるなどの処理）
        val_str = str(elem.value)
        if len(val_str) > 50:
            val_str = val_str[:50] + "..."
            
        header_rows.append({
            "Tag": f"{elem.tag}",       # (0010, 0010) のような形式
            "Name": elem.name,          # "Patient's Name" など
            "VR": elem.VR,              # Value Representation (PN, UI, CSなど)
            "Value": val_str            # 実際の値
        })
        
    return header_rows

def load_dicom_series(folder_path: str) -> DicomSeriesData:
    path = Path(folder_path)
    if not path.is_dir():
        raise ValueError("フォルダが見つかりません")

    dicom_files = []
    for f in path.glob("*"):
        if f.is_file():
            try:
                dcm = pydicom.dcmread(f, stop_before_pixels=True)
                dicom_files.append((f, dcm))
            except:
                continue
    
    if not dicom_files:
        raise ValueError("DICOMファイルが見つかりません")

    # ソート
    dicom_files.sort(key=lambda x: x[1].InstanceNumber if 'InstanceNumber' in x[1] else x[0].name)

    # 最初のファイルのヘッダ情報を代表として取得・整形
    first_dcm_header = pydicom.dcmread(dicom_files[0][0]) # ピクセルごと全部読む必要はないが、ヘッダ解析用に1つ読む
    formatted_header = format_dicom_header(first_dcm_header)

    # 全ボリュームデータの読み込み
    slices = []
    first_dcm = None # メタデータ取得用
    
    for f_path, _ in dicom_files:
        dcm = pydicom.dcmread(f_path)
        if first_dcm is None:
            first_dcm = dcm
        slices.append(dcm.pixel_array)

    volume = np.array(slices)
    
    spacing = getattr(first_dcm, 'PixelSpacing', [1.0, 1.0])
    thickness = getattr(first_dcm, 'SliceThickness', 1.0)
    desc = getattr(first_dcm, 'SeriesDescription', "No Description")
    
    wc = first_dcm.WindowCenter if 'WindowCenter' in first_dcm else 40
    ww = first_dcm.WindowWidth if 'WindowWidth' in first_dcm else 400
    if isinstance(wc, pydicom.multival.MultiValue): wc = wc[0]
    if isinstance(ww, pydicom.multival.MultiValue): ww = ww[0]

    return DicomSeriesData(
        volume=volume,
        pixel_spacing=[float(x) for x in spacing],
        slice_thickness=float(thickness),
        series_description=str(desc),
        header_data=formatted_header, # ここを変更
        window_center=float(wc),
        window_width=float(ww)
    )