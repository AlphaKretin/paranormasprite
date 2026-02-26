# viewer.spec — PyInstaller spec for ParanormaSprite
import glob, os, site as _site
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


def _collect_nested_dlls(package_name):
    """Recursively collect DLLs from a package that nests them in subdirectories
    (e.g. fmod_toolkit/libfmod/Windows/x64/fmod.dll), which collect_dynamic_libs
    misses because it only searches one level deep."""
    for sp in _site.getsitepackages():
        pkg_dir = os.path.join(sp, package_name)
        if os.path.isdir(pkg_dir):
            return [
                (dll, ".")
                for dll in glob.glob(
                    os.path.join(pkg_dir, "**", "*.dll"), recursive=True
                )
            ]
    return []


block_cipher = None

a = Analysis(
    ["app.py"],
    pathex=["."],
    datas=collect_data_files("UnityPy") + collect_data_files("archspec") + [("icon.ico", ".")],
    binaries=(
        collect_dynamic_libs("UnityPy") +
        collect_dynamic_libs("etcpak") +
        collect_dynamic_libs("texture2ddecoder") +
        _collect_nested_dlls("fmod_toolkit")
    ),
    hiddenimports=[
        "lz4", "lz4.frame", "lz4.block",
        "Crypto", # this means cryptography not cryptocurrency
        "PIL._imaging",
        "shiboken6",
        "etcpak", "texture2ddecoder", "pyfmodex", "fmod_toolkit",
    ],
    excludes=["tkinter", "matplotlib", "numpy"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="ParanormaSprite",
    icon="icon.ico",
    console=False,
    onefile=True,
)
