"""Servidor estático de la web de MeshAudit para la app de Mac y MeshAudit.command.

Igual que ``python -m http.server``, pero con ``Cache-Control: no-cache``: así el navegador
revalida HTML, JS y CSS en cada carga y siempre muestra la interfaz actual tras actualizar
el repositorio.

    python app_mac/servidor_web.py <puerto> <carpeta>
"""
from __future__ import annotations

import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class SinCache(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".mjs": "text/javascript"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, formato, *args):  # registro breve en web.log
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), formato % args))


def main() -> None:
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "web"
    manejador = functools.partial(SinCache, directory=carpeta)
    with ThreadingHTTPServer(("127.0.0.1", puerto), manejador) as servidor:
        servidor.serve_forever()


if __name__ == "__main__":
    main()
