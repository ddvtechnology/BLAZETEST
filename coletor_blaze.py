from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from supabase import create_client
import time
import datetime
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://raanrbjruegfqxmnxgpw.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJhYW5yYmpydWVnZnF4bW54Z3B3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyODk1MzgsImV4cCI6MjA5MTg2NTUzOH0.g8YHhDLYdbQAeN08QM5MND3dTxv5CDk2syIevazzZsI")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

URL = "https://blaze.bet.br/pt/games/double"

def salvar_resultado(cor, numero, timestamp):
    try:
        supabase.table("double_results").insert({
            "cor": cor,
            "numero": int(numero),
            "timestamp": timestamp
        }).execute()
        log.info(f"Salvo: {cor} {numero}")
    except Exception as e:
        log.error(f"Erro ao salvar: {e}")

def criar_driver():
    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-zygote")
    options.add_argument("--single-process")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-3d-apis")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

def extrair_resultado(elemento):
    try:
        classes = elemento.get_attribute("class")
        if "white" in classes:
            return ("Branco", "0")
        numero_els = elemento.find_elements(By.CLASS_NAME, "number")
        if not numero_els:
            return None
        numero = numero_els[0].text.strip()
        if not numero:
            return None
        if "red" in classes:
            return ("Vermelho", numero)
        elif "black" in classes:
            return ("Preto", numero)
        return None
    except Exception as e:
        log.debug(f"Erro ao extrair: {e}")
        return None

def capturar_lista(driver, n=5):
    try:
        itens = driver.find_elements(By.CSS_SELECTOR, ".sm-box")
        resultados = []
        for item in itens[:n]:
            r = extrair_resultado(item)
            if r:
                resultados.append(r)
        return resultados
    except Exception:
        return []

def aguardar_pagina(driver, timeout=60):
    seletores = [".entries.main", ".sm-box", "[class*='entries']", "[class*='sm-box']"]
    for seletor in seletores:
        try:
            log.info(f"Aguardando seletor: {seletor}")
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, seletor))
            )
            log.info(f"Encontrado: {seletor}")
            return seletor
        except Exception:
            log.warning(f"Nao encontrado: {seletor}")

    # Diagnóstico
    log.error(f"Titulo: {driver.title}")
    log.error(f"URL: {driver.current_url}")
    log.error(f"HTML parcial: {driver.page_source[:500]}")
    raise Exception("Nenhum seletor encontrado na pagina")

def coletor_continuo():
    RECONEXAO_ESPERA = 15
    POLLING = 2.0
    ERROS_MAX = 5
    REINICIO_MIN = 20

    while True:
        driver = None
        try:
            log.info("Iniciando Chrome...")
            driver = criar_driver()

            log.info(f"Acessando {URL}...")
            driver.get(URL)
            aguardar_pagina(driver, timeout=60)

            log.info("Coletor ativo")
            log.info("-" * 50)

            lista_anterior = capturar_lista(driver, n=5)
            log.info(f"Estado inicial: {lista_anterior}")

            erros_seguidos = 0
            inicio = time.time()

            while True:
                if time.time() - inicio > REINICIO_MIN * 60:
                    log.info(f"Reinicio preventivo após {REINICIO_MIN} min")
                    break

                try:
                    lista_atual = capturar_lista(driver, n=5)

                    if not lista_atual:
                        time.sleep(POLLING)
                        continue

                    if lista_atual and lista_anterior:
                        if lista_atual[0] != lista_anterior[0]:
                            novos = []
                            for item in lista_atual:
                                if item == lista_anterior[0]:
                                    break
                                novos.append(item)

                            for cor, numero in reversed(novos):
                                timestamp = datetime.datetime.now()
                                emoji = {"Branco": "⚪", "Vermelho": "🔴", "Preto": "⚫"}.get(cor, "?")
                                log.info(f"{emoji} {cor} {numero}")
                                salvar_resultado(cor, numero, timestamp.isoformat())

                            lista_anterior = lista_atual

                    elif lista_atual and not lista_anterior:
                        lista_anterior = lista_atual

                    erros_seguidos = 0

                except Exception as e:
                    erros_seguidos += 1
                    log.warning(f"Erro no loop ({erros_seguidos}/{ERROS_MAX}): {type(e).__name__}")
                    if erros_seguidos >= ERROS_MAX:
                        log.error("Muitos erros, reiniciando Chrome...")
                        break

                time.sleep(POLLING)

        except KeyboardInterrupt:
            log.info("Parado pelo usuario.")
            break

        except Exception as e:
            log.error(f"Erro critico: {e}. Reconectando em {RECONEXAO_ESPERA}s...")
            time.sleep(RECONEXAO_ESPERA)

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

if __name__ == "__main__":
    coletor_continuo()