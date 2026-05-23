FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    CHROME_BINARY_PATH=/usr/bin/chromium

# Dependências de sistema:
# - chromium ............ navegador que a automação controla
# - xvfb ................ tela virtual (não há monitor real no container)
# - fluxbox ............. window manager leve (posiciona/foca as janelas)
# - xclip ............... backend de clipboard usado pelo pyperclip no Linux
# - scrot ............... captura de tela usada pelo pyscreeze (locateOnScreen)
# - libtk8.6/libtcl8.6 .. runtime Tcl/Tk; sem ele o mouseinfo (dep do pyautogui)
#                         chama sys.exit() no import e derruba o app
# - libgl1/glib/... ..... runtime do OpenCV (image matching com confidence=)
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        xvfb \
        fluxbox \
        x11-utils \
        xclip \
        scrot \
        libtk8.6 \
        libtcl8.6 \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# python-xlib: backend X11 que o PyAutoGUI usa para mover/clicar/digitar no Linux
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt python-xlib

COPY . .

RUN chmod +x /app/docker/start.sh

EXPOSE 8501

CMD ["/app/docker/start.sh"]
