#!/bin/zsh
# Genera app_mac/MeshAudit.app a partir de MeshAudit.applescript (applet que se queda abierto).
#   zsh app_mac/crear_app.sh
set -eu
CARPETA="${0:A:h}"
APP="$CARPETA/MeshAudit.app"

rm -rf "$APP"
osacompile -s -o "$APP" "$CARPETA/MeshAudit.applescript"
chmod +x "$CARPETA/meshaudit.sh"

# Nombre e identificador del paquete
PLIST="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName MeshAudit" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string mx.meshaudit.app" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier mx.meshaudit.app" "$PLIST"

# Icono (opcional): app_mac/icono.icns
if [[ -f "$CARPETA/icono.icns" ]]; then
  cp "$CARPETA/icono.icns" "$APP/Contents/Resources/applet.icns"
fi

touch "$APP"
print "Creada: $APP"
