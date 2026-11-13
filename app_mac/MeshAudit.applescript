-- MeshAudit.app: applet que se queda abierto. Al abrirlo arranca Ollama, la API y la web
-- con meshaudit.sh (en la misma carpeta que la app) y abre el navegador; al salir, las detiene.

property urlWeb : "http://localhost:5173"

on guion()
	set carpeta to do shell script "dirname " & quoted form of POSIX path of (path to me)
	return quoted form of (carpeta & "/meshaudit.sh")
end guion

on run
	display notification "Iniciando Ollama, la API y la web…" with title "MeshAudit"
	try
		do shell script "/bin/zsh " & guion() & " iniciar"
	on error mensaje
		display dialog "MeshAudit no pudo arrancar:" & return & return & mensaje buttons {"Salir"} default button 1 with icon stop with title "MeshAudit"
		quit
		return
	end try
	open location urlWeb
end run

on reopen
	open location urlWeb
end reopen

on quit
	try
		do shell script "/bin/zsh " & guion() & " detener"
	end try
	continue quit
end quit
