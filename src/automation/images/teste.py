import pyautogui
import time
from pathlib import Path

IMAGES_DIR = Path(__file__).parent


def _clicar_imagem(img: str, timeout: int = 10) -> bool:
    img_path = str(IMAGES_DIR / img)
    centro = None
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            centro = pyautogui.locateCenterOnScreen(img_path, confidence=0.9)
            if centro is not None:
                break
        except pyautogui.ImageNotFoundException:
            pass
        time.sleep(0.5)

    if centro is None:
        print("Erro! Imagem não encontrada")
        return False

    pyautogui.click(centro)
    print("Clicado com sucesso")
    return True


if __name__ == "__main__":
    _clicar_imagem("btn_consultar.png", timeout=10)
