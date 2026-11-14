#!/bin/zsh
# Doble clic en Finder para abrir MeshAudit en Terminal.
# Arranca Ollama, la API (:8000) y la web (:5173), abre el navegador y,
# al pulsar Enter o cerrar la ventana, detiene la API y la web (Ollama sigue abierto).
RAIZ="${0:A:h}"
SCRIPT="$RAIZ/app_mac/meshaudit.sh"

trap '/bin/zsh "$SCRIPT" detener; print "MeshAudit detenido."' EXIT INT TERM HUP

print "Iniciando MeshAudit… (la primera vez puede tardar hasta un minuto)"
if ! /bin/zsh "$SCRIPT" iniciar; then
  print "\nNo se pudo iniciar. Registros en ~/Library/Logs/MeshAudit/"
  read -r "?Pulsa Enter para cerrar."
  exit 1
fi

open "http://localhost:5173"
print "\nMeshAudit está en marcha: http://localhost:5173"
print "Mallas de ejemplo para probar: $RAIZ/ejemplos/"
read -r "?Pulsa Enter para detenerlo."
