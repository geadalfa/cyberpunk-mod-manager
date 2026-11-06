# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static'), ('engine', 'engine'), ('app_icon.ico', '.')],
    hiddenimports=['engine.config_manager', 'engine.nexus_client', 'engine.mod_installer'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CyberpunkModManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CyberpunkModManager',
)
