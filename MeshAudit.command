#!/bin/zsh
# Doble clic en Finder para abrir MeshAudit en Terminal.
# Arranca Ollama, la API (:8000) y la web (:5173) con el código actual del repositorio,
# abre el navegador y, al pulsar Enter o cerrar la ventana, detiene la API y la web
# (Ollama sigue abierto).
RAIZ="${0:A:h}"
SCRIPT="$RAIZ/app_mac/meshaudit.sh"
URL="http://localhost:5173"

trap '/bin/zsh "$SCRIPT" detener; print "\nMeshAudit detenido."' EXIT INT TERM HUP

print "Iniciando MeshAudit… (la primera vez puede tardar hasta un minuto)"
if ! /bin/zsh "$SCRIPT" reiniciar; then
  print "\nNo se pudo iniciar. Registros en ~/Library/Logs/MeshAudit/"
  read -r "?Pulsa Enter para cerrar."
  exit 1
fi

open "$URL"
cat <<EOF

MeshAudit está en marcha: $URL

  1. «Abrir malla» o arrastra un .obj, .glb, .stl o .ply a la vista 3D.
  2. Elige el perfil y pulsa «Auditar».
  3. Selecciona un hallazgo en el Outliner para ver su explicación en Atributos.
  4. Pregunta sobre el informe en la línea «Consulta» de abajo.

  Vista 3D: F encuadrar · 4 alambre · 5 sombreado · 6 texturas · W alambre encima
            B caras traseras · E bordes · G rejilla
  Ratón:    arrastrar orbita · clic derecho desplaza · rueda acerca

  Mallas de ejemplo: $RAIZ/ejemplos/
  Registros:         ~/Library/Logs/MeshAudit/

EOF
read -r "?Pulsa Enter para detenerlo."
