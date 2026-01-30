# dicom画像(ctまたはmri)系列ビューア

[マニュアル](doc/manual.md)

[ダウンロード](src/dist/MedViewer.exe)

## 開発

python, napari, pydicomを利用

もし起動できない場合は、ソースから試してください:

```powerhshell
cd src/
python -m venv .venv
.venv\Scripts\activate.ps1
pip install -r requirements.txt
python main.py
```

ビルドは以下

```powershell
pyinstaller main.py --name="MedViewer" --onefile --noconsole --collect-all napari --collect-all magicgui --collect-all vispy --hidden-import=pydicom --copy-metadata=imageio --copy-metadata=napari
```
