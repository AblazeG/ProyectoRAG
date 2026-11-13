#!/bin/zsh
# Arranca y detiene MeshAudit en este Mac: Ollama, la API (uvicorn :8000) y la web (:5173).
# Lo usa MeshAudit.app; también sirve desde la terminal:
#   app_mac/meshaudit.sh iniciar | detener | estado
set -u

RAIZ="${0:A:h:h}"                                  # raíz del repositorio
PY="$RAIZ/.venv/bin/python"
SOPORTE="$HOME/Library/Application Support/MeshAudit"
REGISTROS="$HOME/Library/Logs/MeshAudit"
API=8000
WEB=5173
mkdir -p "$SOPORTE" "$REGISTROS"

escuchando() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

esperar() {   # esperar <url> <segundos>
  local i=0
  until curl -fs -o /dev/null "$1"; do
    (( i++ >= $2 )) && return 1
    sleep 1
  done
}

fallar() { print -u2 -- "$1"; exit 1; }

iniciar() {
  [[ -x "$PY" ]] || fallar "No encuentro el entorno de Python en $RAIZ/.venv. Crea el entorno siguiendo el README."

  # 1. Ollama (la app de menú; sin red: OLLAMA_NO_CLOUD ya está en launchctl)
  if ! curl -fs -o /dev/null http://127.0.0.1:11434/api/version; then
    open -ga Ollama 2>/dev/null || fallar "Ollama no está instalado (/Applications/Ollama.app)."
    esperar http://127.0.0.1:11434/api/version 60 || fallar "Ollama no respondió en 60 s."
  fi

  # 2. API
  if ! escuchando $API; then
    cd "$RAIZ"
    nohup "$PY" -m uvicorn servicio.composicion:app --host 127.0.0.1 --port $API \
      >> "$REGISTROS/api.log" 2>&1 &
    print $! > "$SOPORTE/api.pid"
  fi

  # 3. Web estática
  if ! escuchando $WEB; then
    nohup "$PY" -m http.server $WEB --bind 127.0.0.1 -d "$RAIZ/web" \
      >> "$REGISTROS/web.log" 2>&1 &
    print $! > "$SOPORTE/web.pid"
  fi

  esperar http://127.0.0.1:$API/health 90 || fallar "La API no arrancó en 90 s. Revisa $REGISTROS/api.log."
  esperar http://127.0.0.1:$WEB/ 15 || fallar "La web no arrancó. Revisa $REGISTROS/web.log."
  print "listo"
}

detener() {   # solo detiene lo que arrancó esta app; Ollama se queda abierto
  local f pid
  for f in api web; do
    [[ -f "$SOPORTE/$f.pid" ]] || continue
    pid=$(<"$SOPORTE/$f.pid")
    kill "$pid" 2>/dev/null
    rm -f "$SOPORTE/$f.pid"
  done
}

estado() {
  escuchando $API && print "API: en marcha (:$API)" || print "API: detenida"
  escuchando $WEB && print "Web: en marcha (:$WEB)" || print "Web: detenida"
  curl -fs -o /dev/null http://127.0.0.1:11434/api/version && print "Ollama: en marcha" || print "Ollama: detenido"
}

case "${1:-iniciar}" in
  iniciar) iniciar ;;
  detener) detener ;;
  estado)  estado ;;
  *) fallar "Uso: $0 iniciar|detener|estado" ;;
esac
