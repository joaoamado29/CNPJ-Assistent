"""BotCity Web automation for consulting the Simples Nacional portal."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import time
import pyautogui
import pyperclip
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


IMAGES_DIR = Path(__file__).parent / "images"


# Force xclip backend on Linux. Pyperclip auto-detects WSL inside Docker Desktop
# (kernel reports "Microsoft") and tries powershell.exe, which fails in container.
if sys.platform.startswith("linux"):
    try:
        pyperclip.set_clipboard("xclip")
    except pyperclip.PyperclipException:
        pass

logger = logging.getLogger(__name__)

PORTAL_URL = "https://consopt.www8.receita.fazenda.gov.br/consultaoptantes"

@dataclass
class ConsultaResult:
    cnpj: str
    success: bool
    nome_empresarial: str | None = None
    situacao_simples: str | None = None
    situacao_simei: str | None = None
    periodos_anteriores_sn: str | None = None
    periodos_anteriores_simei: str | None = None
    eventos_futuros_sn: str | None = None
    eventos_futuros_simei: str | None = None
    mei_transportador_autonomo_cargas: str | None = None
    raw_text: str | None = None
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class SimplesNacionalBot():

    def __init__(self) -> None:
        self._abrir_chrome()

    def _clicar_imagem(self, img: str, timeout: int = 10, confidence: float = 0.7) -> bool:
        img_path = str(IMAGES_DIR / img)
        centro = None
        fim = time.time() + timeout
        while time.time() < fim:
            try:
                centro = pyautogui.locateCenterOnScreen(img_path, confidence=confidence)
                if centro is not None:
                    break
            except pyautogui.ImageNotFoundException:
                pass
            time.sleep(0.5)

        if centro is None:
            logger.warning(f"Botão '{img}' não encontrada em {timeout}s.")
            return False

        pyautogui.click(centro)
        logger.info(f"Botão '{img}' clicada com sucesso.")
        return True

    def consultar(self, cnpj: str):
        dados_brutos = self._consultar_cnpj(cnpj)
        return self._tratar_dados(dados_brutos)
    # abrir chrome
    def _abrir_chrome(self) -> None:
        logger.info("Abrindo o navegador Chrome...")
        chrome_path = os.getenv("CHROME_BINARY_PATH") or (
            "chrome.exe" if sys.platform == "win32" else "google-chrome"
        )

        if sys.platform == "win32":
            if chrome_path == "chrome.exe":
                os.startfile(chrome_path)
            else:
                subprocess.Popen(
                    [chrome_path, PORTAL_URL],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            time.sleep(0.5)  # Espera o Chrome abrir
            if chrome_path == "chrome.exe":
                pyautogui.hotkey('ctrl', 'l')  # Foca a barra de endereços
                time.sleep(1)
                pyautogui.write(PORTAL_URL)
                pyautogui.press('enter')
        else:
            # Linux/container: open Chrome with URL directly + sandbox flags required for root.
            subprocess.Popen(
                [
                    chrome_path,
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--user-data-dir=/tmp/chrome-data",
                    "--no-first-run",
                    "--no-default-browser-check",
                    PORTAL_URL,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        self._clicar_imagem("btn_consultar.png", timeout=5) # GAMBIARRA ver se a tela carregou
    # consultar cnpj e extrair dados
    def _consultar_cnpj(self, cnpj: str) -> str:
        logger.info(f"Consultando CNPJ: {cnpj}")
        self._clicar_imagem("cnpj_input.png", timeout=5)
        pyautogui.write(cnpj)  # Digita o CNPJ
        time.sleep(1)  # Espera o texto ser processado
        logger.info("CNPJ digitado, realizando consulta...")


        if not self._clicar_imagem("btn_maisinfo.png", timeout=3):
            logger.warning("CNPJ não encontrado na base de dados")
            return ""

        pyautogui.hotkey('ctrl', 'a')  # Seleciona todo o texto
        pyautogui.hotkey('ctrl', 'c')  # Copia o texto selecionado
        logger.info("Dados copiados para a área de transferência, processando...")
        dados_brutos = pyperclip.paste()  # Obtém o texto copiado
        return dados_brutos
    # tratar e retornar dados
    def _tratar_dados(self, dados_brutos: str) -> ConsultaResult:
        if "inválido" in dados_brutos.lower():
            print("CNPJ inválido")
            return ConsultaResult(
                cnpj="",
                success=False,
                error="CNPJ inválido",
                raw_text=dados_brutos
            )
        
        else:
            dados_brutos = dados_brutos.split()
            print(dados_brutos)
            i_aux = dados_brutos.index("CNPJ:") + 1
            cnpj = dados_brutos[i_aux]
            success = True

            i_aux = dados_brutos.index("Empresarial:") + 1
            i_aux2 = dados_brutos.index("Situação")
            nome_empresarial = " ".join(dados_brutos[i_aux:i_aux2])
            
            i_aux = dados_brutos.index("Nacional:") + 1
            i_aux2 = dados_brutos.index("Situação", i_aux)
            situacao_simples = " ".join(dados_brutos[i_aux:i_aux2])
            
            i_aux = dados_brutos.index("SIMEI:") + 1
            i_aux2 = dados_brutos.index("Períodos", i_aux)
            situacao_simei = " ".join(dados_brutos[i_aux:i_aux2])

    # PERÍODOS ANTERIORES SIMPLES NACIONAL E SIMEI

        i_aux = dados_brutos.index("Opções") + 7
        i_aux2 = dados_brutos.index("Enquadramentos")
        periodos_anteriores_sn = " ".join(dados_brutos[i_aux:i_aux2])
        print(f"Períodos anteriores Simples Nacional: {periodos_anteriores_sn}")

        i_aux = dados_brutos.index("Enquadramentos") + 6
        i_aux2 = dados_brutos.index("Futuros") - 1
        periodos_anteriores_simei = " ".join(dados_brutos[i_aux:i_aux2])
        print(f"Períodos anteriores SIMEI: {periodos_anteriores_simei}")

    # TRATEMENTOS ANTERIORES SIMEI E SIMPLES NACIONAL

        # SN:
        if periodos_anteriores_sn == "Não Existem":
            pass
        else:
            aux_list = periodos_anteriores_sn.split()
            i_aux = aux_list.index("Detalhamento") + 1
            i_aux2 = aux_list.index("Detalhamento") + 3
            periodos_anteriores_sn = " - ".join(aux_list[i_aux:i_aux2])
            print(f"Período Simples Nacional: {periodos_anteriores_sn}")

        # SIMEI:
        if periodos_anteriores_simei == "Não Existem":
            pass
        else:
            aux_list = periodos_anteriores_simei.split()
            i_aux = aux_list.index("Detalhamento") + 1
            i_aux2 = aux_list.index("Detalhamento") + 3
            periodos_anteriores_simei = " - ".join(aux_list[i_aux:i_aux2])
            print(f"Período SIMEI: {periodos_anteriores_simei}")

    # EVENTOS FUTUROS SIMPLES NACIONAL E SIMEI    
        i_aux = dados_brutos.index("Nacional)") + 1
        i_aux2 = dados_brutos.index("Eventos", i_aux)
        eventos_futuros_sn = " ".join(dados_brutos[i_aux:i_aux2])
        print(f"Eventos futuros Simples Nacional: {eventos_futuros_sn}")

        i_aux = dados_brutos.index("(SIMEI)") + 1
        i_aux2 = dados_brutos.index("Informações", i_aux)
        eventos_futuros_simei = " ".join(dados_brutos[i_aux:i_aux2])
        print(f"Eventos futuros SIMEI: {eventos_futuros_simei}")

    # MEI TRANSPORTADOR AUTÔNOMO DE CARGAS
        i_aux = dados_brutos.index("Cargas") + 1
        mei_transportador_autonomo_cargas = " ".join(dados_brutos[i_aux:])
        print(f"MEI Transportador Autônomo de Cargas: {mei_transportador_autonomo_cargas}")

        # Retorna um objeto ConsultaResult com os dados extraídos
        return ConsultaResult(
            cnpj=cnpj,
            success=success,
            nome_empresarial=nome_empresarial,
            situacao_simples=situacao_simples,
            situacao_simei=situacao_simei,
            periodos_anteriores_sn=periodos_anteriores_sn,
            periodos_anteriores_simei=periodos_anteriores_simei,
            eventos_futuros_sn=eventos_futuros_sn,
            eventos_futuros_simei=eventos_futuros_simei,
            mei_transportador_autonomo_cargas=mei_transportador_autonomo_cargas,
            raw_text=dados_brutos
        )

    def close(self) -> None:
        logger.info("Fechando o navegador Chrome...")
        pyautogui.hotkey('alt', 'f4')  # Pressiona Alt + F4 para fechar a janela ativa do Chrome
        time.sleep(1)  # Espera o Chrome fechar completamente
