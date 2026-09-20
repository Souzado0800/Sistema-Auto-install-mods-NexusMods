#!/usr/bin/env bash
# ==============================================================================
# Restarts Brave gracefully with Chromium DevTools Protocol (CDP) on port 9222
# Preserves all active tabs, session logins, and cookies.
# ==============================================================================
set -e

echo "[*] Encerrando o Brave de forma segura para persistir as abas abertas..."
pkill -15 -f "/opt/brave.com/brave/brave" 2>/dev/null || true
sleep 2

echo "[*] Reabrindo o Brave com a porta oficial de depuração/automação 9222..."
nohup env DISPLAY="${DISPLAY:-:1}" /usr/bin/brave-browser-stable --remote-debugging-port=9222 --restore-last-session >/dev/null 2>&1 &
sleep 2

if curl -s http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
    echo "[✓] Automação oficial CDP conectada com sucesso na porta 9222!"
else
    sleep 1
    if curl -s http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
        echo "[✓] Automação oficial CDP conectada com sucesso na porta 9222!"
    else
        echo "[!] O Brave foi reiniciado. Verifique a abertura na sua tela."
    fi
fi
