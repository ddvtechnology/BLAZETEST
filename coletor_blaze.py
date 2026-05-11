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

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ==============================
# SUPABASE
# ==============================
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://raanrbjruegfqxmnxgpw.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJhYW5yYmpydWVnZnF4bW54Z3B3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyODk1MzgsImV4cCI6MjA5MTg2NTUzOH0.g8YHhDLYdbQAeN08QM5MND3dTxv5CDk2syIevazzZsI")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

URL = "https://blaze.bet.br/pt/games/double"

# ==============================
# SUPABASE: SALVAR
# ==============================
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

# ==============================
# CHROME: CRIAR DRIVER
# ==============================
def criar_driver():
    options = Options()

    # --- Binários do Chromium (instalado via apt) ---
    options.binary_location = "/usr/bin/chromium"

    # --- Headless obrigatório em servidor ---
    options.add_argument("--headless=new")

    # --- Crítico para containers ---
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-zygote")
    options.add_argument("--single-process")

    # --- GPU / rendering ---
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-3d-apis")

    # --- Reduz uso de memória ---
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")

    # --- Janela ---
    options.add_argument("--window-size=1280,800")

    # --- Anti-detecção de bot ---
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # --- User-Agent real ---
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    # --- ChromeDriver do Chromium ---
    service = Service("/usr/bin/chromedriver")

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)

    # Remove flag webdriver do JS
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    return driver

# ==============================
# EXTRAI RESULTADO
# ==============================
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

# ==============================
# AGUARDA PAGINA CARREGAR
# ==============================
def aguardar_pagina(driver, timeout=60):
    seletores = [
        ".entries.main",
        ".sm-box",
        "[class*='entries']",
        "[class*='sm-box']",
    ]

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
            continue

    log.error(f"Titulo da pagina: {driver.title}")
    log.error(f"URL atual: {driver.current_url}")

    raise Exception("Nenhum seletor encontrado na pagina")

# ==============================
# LOOP PRINCIPAL
# ==============================
def coletor_continuo():
    RECONEXAO_ESPERA = 15
    POLLING = 0.3

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

            ultimo_id = None

            while True:
                try:
                    itens = driver.find_elements(By.CSS_SELECTOR, ".sm-box")

                    if not itens:
                        time.sleep(POLLING)
                        continue

                    primeiro = itens[0]
                    elem_id = primeiro.id

                    if elem_id == ultimo_id:
                        time.sleep(POLLING)
                        continue

                    resultado = extrair_resultado(primeiro)
                    if resultado is None:
                        time.sleep(POLLING)
                        continue

                    cor, numero = resultado
                    timestamp = datetime.datetime.now()
                    emoji = {"Branco": "⚪", "Vermelho": "🔴", "Preto": "⚫"}.get(cor, "?")

                    log.info(f"{emoji} {cor} {numero}")
                    salvar_resultado(cor, numero, timestamp.isoformat())
                    ultimo_id = elem_id

                except Exception as e:
                    log.warning(f"Erro no loop: {e}")

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