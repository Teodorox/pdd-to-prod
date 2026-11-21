"""pyautogui: ÚLTIMO recurso, só para o que não é web (aplicativo desktop, diálogo nativo do Windows).

Instale com: uv sync --extra desktop   (confianca= exige também opencv-python)
"""

import logging
import time
from pathlib import Path
from types import ModuleType

log = logging.getLogger(__name__)


class ImagemNaoEncontrada(Exception):
    pass


def _pyautogui() -> ModuleType:
    try:
        import pyautogui
    except ImportError as exc:
        raise ImportError("pyautogui não instalado. Rode: uv sync --extra desktop") from exc
    pyautogui.FAILSAFE = True  # mouse no canto superior esquerdo aborta
    return pyautogui


def clicar_imagem(imagem: Path, *, timeout_s: float = 10, confianca: float | None = None) -> None:
    """Procura a imagem na tela até `timeout_s` e clica no centro. Guarde as imagens em docs/ ou dados/."""
    pg = _pyautogui()
    kwargs = {"confidence": confianca} if confianca is not None else {}
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        try:
            ponto = pg.locateCenterOnScreen(str(imagem), **kwargs)
        except pg.ImageNotFoundException:
            ponto = None
        if ponto is not None:
            log.info("Clicando na imagem %s em %s", imagem.name, ponto)
            pg.click(ponto)
            return
        time.sleep(0.5)
    raise ImagemNaoEncontrada(f"{imagem} não apareceu na tela em {timeout_s}s")


def digitar(texto: str, *, intervalo_s: float = 0.02) -> None:
    _pyautogui().write(texto, interval=intervalo_s)


def tecla(*teclas: str) -> None:
    """tecla("enter") ou tecla("ctrl", "s")."""
    pg = _pyautogui()
    pg.hotkey(*teclas) if len(teclas) > 1 else pg.press(teclas[0])
