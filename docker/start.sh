#!/bin/bash
# Sobe a tela virtual + window manager e então a interface Streamlit.
# A automação (PyAutoGUI) usa esse mesmo display :99 para controlar o Chromium.
set -e

# Remove lock de execução anterior, se houver
rm -f /tmp/.X99-lock

# Tela virtual 1920x1080 (a resolução afeta o casamento das imagens da automação)
Xvfb :99 -screen 0 1920x1080x24 -ac +extension RANDR &
export DISPLAY=:99

# Espera o display ficar pronto
for i in $(seq 1 10); do
    xdpyinfo -display :99 >/dev/null 2>&1 && break
    sleep 0.5
done

# Window manager (sem ele as janelas do Chrome não recebem foco corretamente)
fluxbox >/dev/null 2>&1 &
sleep 1

# Worker da fila: processo separado, supervisionado (reergue se cair). Roda em
# segundo plano independente do navegador — fechar a aba do celular não o afeta.
# Herda o mesmo DISPLAY=:99 para controlar o Chromium na tela virtual.
(
    while true; do
        echo "[start] iniciando worker da fila..."
        python -u worker.py || echo "[start] worker saiu (code $?); reinicia em 2s"
        sleep 2
    done
) &

exec streamlit run app.py \
    --server.address=0.0.0.0 \
    --server.port=8501 \
    --server.headless=true
