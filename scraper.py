"""
Script principal para extraer datos de empresas del sistema SAÓ FCT
"""
import os
import time
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from models import EmpresaCompleta, ScrapingResult


class SAOScraper:
    """Clase principal para el scraping del sistema SAÓ FCT"""
    
    def __init__(self, headless: bool = False):
        """
        Inicializa el scraper
        
        Args:
            headless: Si True, ejecuta el navegador en modo headless
        """
        self.headless = headless
        self.driver = None
        self.wait = None
        self.empresas: List[EmpresaCompleta] = []
        self.errores = 0
        
        # Configurar logging
        self._setup_logging()
        
        # Cargar variables de entorno
        load_dotenv()
        
        # Verificar credenciales
        self.usuario = os.getenv('SAO_USUARIO')
        self.password = os.getenv('SAO_PASSWORD')
        
        if not self.usuario or not self.password:
            raise ValueError("Credenciales no encontradas en .env. Verifica SAO_USUARIO y SAO_PASSWORD")

    def _setup_logging(self):
        """Configura el sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _setup_driver(self):
        """Configura el WebDriver (Firefox por defecto, Chrome como alternativa)"""
        # Intentar Firefox primero (funciona mejor en tu sistema)
        try:
            from selenium.webdriver.firefox.service import Service as FirefoxService
            from webdriver_manager.firefox import GeckoDriverManager
            
            self.logger.info("Configurando Firefox WebDriver...")
            
            firefox_options = webdriver.FirefoxOptions()
            if self.headless:
                firefox_options.add_argument("--headless")
            
            firefox_options.add_argument("--no-sandbox")
            firefox_options.add_argument("--disable-dev-shm-usage")
            
            service = FirefoxService(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=firefox_options)
            self.wait = WebDriverWait(self.driver, 10)
            
            self.logger.info("WebDriver Firefox configurado correctamente")
            return
            
        except Exception as e:
            self.logger.warning(f"Firefox no disponible: {e}")
        
        # Fallback a Chrome si Firefox falla
        try:
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
            
            self.logger.info("Configurando Chrome WebDriver...")
            
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Intentar con versión específica
            try:
                service = Service(ChromeDriverManager(version="119.0.6045.105").install())
            except:
                service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)
            
            self.logger.info("WebDriver Chrome configurado correctamente")
            
        except Exception as e:
            self.logger.error(f"Error configurando Chrome: {e}")
            raise Exception(f"No se pudo configurar ningún navegador. Firefox y Chrome fallaron.")

    def login(self) -> bool:
        """
        Realiza el login en el sistema SAÓ FCT
        
        Returns:
            bool: True si el login fue exitoso
        """
        try:
            self.logger.info("Iniciando proceso de login...")
            
            # Navegar a la página de login
            login_url = "https://foremp.edu.gva.es/index.php?op=4&subop=0"
            self.driver.get(login_url)
            
            # Esperar a que cargue la página
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
            
            # Localizar campos de usuario y contraseña
            # Nota: Los selectores exactos se ajustarán tras la primera ejecución
            usuario_field = self.driver.find_element(By.NAME, "usuario")  # Ajustar según HTML real
            password_field = self.driver.find_element(By.NAME, "password")  # Ajustar según HTML real
            
            # Rellenar credenciales
            usuario_field.clear()
            usuario_field.send_keys(self.usuario)
            
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Enviar formulario
            submit_button = self.driver.find_element(By.XPATH, "//input[@type='submit']")
            submit_button.click()
            
            # Esperar a que cargue la página principal
            time.sleep(3)
            
            # Verificar si el login fue exitoso (ajustar según la respuesta del sistema)
            if "error" in self.driver.current_url.lower() or "login" in self.driver.current_url.lower():
                self.logger.error("Error en el login - credenciales incorrectas o página de error")
                return False
            
            self.logger.info("Login exitoso")
            return True
            
        except TimeoutException:
            self.logger.error("Timeout esperando elementos de login")
            return False
        except NoSuchElementException as e:
            self.logger.error(f"Elemento no encontrado en login: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado en login: {e}")
            return False

    def extraer_listado_empresas(self) -> List[EmpresaCompleta]:
        """
        Extrae el listado principal de empresas
        
        Returns:
            List[EmpresaCompleta]: Lista de empresas con datos básicos
        """
        try:
            self.logger.info("Extrayendo listado de empresas...")
            
            # Navegar a la página del listado de empresas
            listado_url = "https://foremp.edu.gva.es/index.php?op=4&subop=0"
            self.driver.get(listado_url)
            self.logger.info(f"Navegando a: {listado_url}")
            
            # Esperar a que cargue la página
            time.sleep(3)
            
            # Buscar tabla de empresas con diferentes selectores
            tabla_empresas = None
            selectores_tabla = [
                "table",
                "table[class*='empresa']",
                "table[class*='list']",
                "table[class*='data']",
                ".tabla-empresas",
                "#tabla-empresas"
            ]
            
            for selector in selectores_tabla:
                try:
                    tabla_empresas = self.driver.find_element(By.CSS_SELECTOR, selector)
                    self.logger.info(f"Tabla encontrada con selector: {selector}")
                    break
                except:
                    continue
            
            if not tabla_empresas:
                # Si no encuentra tabla, buscar cualquier elemento que contenga enlaces con idEmpresa
                self.logger.info("No se encontró tabla, buscando enlaces con idEmpresa...")
                enlaces_empresas = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'idEmpresa')]")
                
                if enlaces_empresas:
                    self.logger.info(f"Encontrados {len(enlaces_empresas)} enlaces de empresas")
                    return self._extraer_empresas_desde_enlaces(enlaces_empresas)
                else:
                    self.logger.error("No se encontraron enlaces de empresas")
                    return []
            
            empresas = []
            filas = tabla_empresas.find_elements(By.TAG_NAME, "tr")
            
            for i, fila in enumerate(filas[1:], 1):  # Saltar encabezado
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    
                    if len(celdas) >= 3:  # Mínimo 3 columnas esperadas
                        # Extraer id_empresa del enlace
                        enlace = fila.find_element(By.TAG_NAME, "a")
                        href = enlace.get_attribute("href")
                        id_empresa = re.search(r'idEmpresa=(\d+)', href)
                        id_empresa = id_empresa.group(1) if id_empresa else ""
                        
                        # Extraer otros datos (ajustar índices según estructura real)
                        registrado = celdas[1].text.strip() if len(celdas) > 1 else ""
                        ultimo_acceso = celdas[2].text.strip() if len(celdas) > 2 else ""
                        
                        empresa = EmpresaCompleta(
                            id_empresa=id_empresa,
                            registrado=registrado,
                            ultimo_acceso=ultimo_acceso
                        )
                        
                        empresas.append(empresa)
                        self.logger.info(f"Empresa {i}: {id_empresa} - {registrado}")
                        
                except Exception as e:
                    self.logger.warning(f"Error procesando fila {i}: {e}")
                    self.errores += 1
                    continue
            
            self.logger.info(f"Listado extraído: {len(empresas)} empresas")
            return empresas
            
        except TimeoutException:
            self.logger.error("Timeout esperando tabla de empresas")
            return []
        except Exception as e:
            self.logger.error(f"Error extrayendo listado: {e}")
            return []

    def _extraer_empresas_desde_enlaces(self, enlaces_empresas) -> List[EmpresaCompleta]:
        """
        Extrae empresas desde enlaces cuando no hay tabla estructurada
        
        Args:
            enlaces_empresas: Lista de elementos de enlace
            
        Returns:
            List[EmpresaCompleta]: Lista de empresas extraídas
        """
        empresas = []
        
        for i, enlace in enumerate(enlaces_empresas, 1):
            try:
                href = enlace.get_attribute("href")
                id_empresa = re.search(r'idEmpresa=(\d+)', href)
                
                if id_empresa:
                    id_empresa = id_empresa.group(1)
                    
                    # Intentar extraer texto del enlace y elementos circundantes
                    texto_enlace = enlace.text.strip()
                    
                    # Buscar elementos padre que puedan contener más información
                    elemento_padre = enlace.find_element(By.XPATH, "./..")
                    texto_padre = elemento_padre.text.strip()
                    
                    # Crear empresa con datos básicos
                    empresa = EmpresaCompleta(
                        id_empresa=id_empresa,
                        registrado="",  # Se intentará extraer de la página de detalle
                        ultimo_acceso="",  # Se intentará extraer de la página de detalle
                        nombre=texto_enlace if texto_enlace else f"Empresa {id_empresa}"
                    )
                    
                    empresas.append(empresa)
                    self.logger.info(f"Empresa {i}: {id_empresa} - {texto_enlace}")
                    
            except Exception as e:
                self.logger.warning(f"Error procesando enlace {i}: {e}")
                self.errores += 1
                continue
        
        return empresas

    def extraer_detalle_empresa(self, empresa: EmpresaCompleta) -> EmpresaCompleta:
        """
        Extrae los datos detallados de una empresa
        
        Args:
            empresa: Objeto EmpresaCompleta con datos básicos
            
        Returns:
            EmpresaCompleta: Empresa con datos completos
        """
        try:
            # Navegar a la página de detalle
            detalle_url = f"https://foremp.edu.gva.es/index.php?accion=19&idEmpresa={empresa.id_empresa}"
            self.driver.get(detalle_url)
            
            # Esperar a que cargue la página
            time.sleep(2)
            
            # Extraer datos detallados
            # Nota: Los selectores se ajustarán tras la primera ejecución
            try:
                empresa.cif = self._extraer_campo("CIF")
                empresa.nombre = self._extraer_campo("Nombre")
                empresa.direccion = self._extraer_campo("Dirección")
                empresa.provincia = self._extraer_campo("Provincia")
                empresa.localidad = self._extraer_campo("Localidad")
                empresa.cp = self._extraer_campo("CP")
                empresa.telefono = self._extraer_campo("Teléfono")
                empresa.fax = self._extraer_campo("Fax")
                empresa.actividad = self._extraer_campo("Actividad")
                empresa.nombre_gerente = self._extraer_campo("Nombre de gerente")
                empresa.nif_gerente = self._extraer_campo("NIF gerente")
                empresa.email = self._extraer_campo("E-mail")
                empresa.tipo = self._extraer_campo("Tipo")
                
            except Exception as e:
                self.logger.warning(f"Error extrayendo detalles de empresa {empresa.id_empresa}: {e}")
                self.errores += 1
            
            # Delay entre peticiones
            time.sleep(0.5)
            
            return empresa
            
        except Exception as e:
            self.logger.error(f"Error navegando a detalle de empresa {empresa.id_empresa}: {e}")
            self.errores += 1
            return empresa

    def _extraer_campo(self, nombre_campo: str) -> str:
        """
        Extrae un campo específico de la página de detalle
        
        Args:
            nombre_campo: Nombre del campo a extraer
            
        Returns:
            str: Valor del campo o cadena vacía si no se encuentra
        """
        try:
            # Buscar en la tabla con clase "infoUsuario infoEmpresa"
            tabla = self.driver.find_element(By.CSS_SELECTOR, "table.infoUsuario.infoEmpresa")
            filas = tabla.find_elements(By.TAG_NAME, "tr")
            
            # Mapeo de campos a posiciones basado en la estructura HTML real
            mapeo_campos = {
                "cif": 0,
                "nombre": 1, 
                "direccion": 3,
                "provincia": 4,
                "localidad": 5,
                "cp": 6
            }
            
            # Buscar en la primera sección (filas 0-1)
            if len(filas) >= 2:
                encabezados = filas[0].find_elements(By.TAG_NAME, "th")
                valores = filas[1].find_elements(By.TAG_NAME, "td")
                
                # Buscar por nombre del campo en encabezados
                for i, encabezado in enumerate(encabezados):
                    if nombre_campo.lower() in encabezado.text.lower():
                        if i < len(valores):
                            return valores[i].text.strip()
                        break
                
                # Buscar por posición si no se encuentra por nombre
                campo_lower = nombre_campo.lower()
                if campo_lower in mapeo_campos:
                    pos = mapeo_campos[campo_lower]
                    if pos < len(valores):
                        return valores[pos].text.strip()
            
            # Buscar en la segunda sección (filas 2-3) para campos como teléfono, fax, etc.
            if len(filas) >= 4:
                encabezados_segunda = filas[2].find_elements(By.TAG_NAME, "th")
                valores_segunda = filas[3].find_elements(By.TAG_NAME, "td")
                
                for i, encabezado in enumerate(encabezados_segunda):
                    if nombre_campo.lower() in encabezado.text.lower():
                        if i < len(valores_segunda):
                            return valores_segunda[i].text.strip()
                        break
            
            return ""
            
        except Exception as e:
            self.logger.warning(f"Error extrayendo campo '{nombre_campo}': {e}")
            return ""

    def extraer_todas_empresas(self) -> ScrapingResult:
        """
        Proceso completo de extracción de todas las empresas
        
        Returns:
            ScrapingResult: Resultado completo del scraping
        """
        inicio = datetime.now()
        
        try:
            # Configurar driver
            self._setup_driver()
            
            # Login
            if not self.login():
                raise Exception("Error en el login")
            
            # Extraer listado
            empresas = self.extraer_listado_empresas()
            
            if not empresas:
                raise Exception("No se encontraron empresas en el listado")
            
            # Extraer detalles de cada empresa
            self.logger.info(f"Procesando {len(empresas)} empresas...")
            
            for i, empresa in enumerate(empresas, 1):
                self.logger.info(f"Procesando empresa {i}/{len(empresas)}: {empresa.id_empresa}")
                empresa_completa = self.extraer_detalle_empresa(empresa)
                self.empresas.append(empresa_completa)
            
            # Calcular tiempo total
            fin = datetime.now()
            tiempo_total = str(fin - inicio)
            
            resultado = ScrapingResult(
                empresas=self.empresas,
                timestamp=inicio.isoformat(),
                total_empresas=len(self.empresas),
                errores=self.errores,
                tiempo_total=tiempo_total
            )
            
            self.logger.info(f"Scraping completado: {len(self.empresas)} empresas en {tiempo_total}")
            return resultado
            
        except Exception as e:
            self.logger.error(f"Error en el proceso de scraping: {e}")
            raise
        finally:
            self.cerrar_navegador()

    def cerrar_navegador(self):
        """Cierra el navegador y libera recursos"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Navegador cerrado")
            except Exception as e:
                self.logger.warning(f"Error cerrando navegador: {e}")


def main():
    """Función principal"""
    try:
        # Crear directorio de salida
        Path("output").mkdir(exist_ok=True)
        
        # Inicializar scraper
        scraper = SAOScraper(headless=False)  # Cambiar a True para ejecución sin interfaz
        
        # Ejecutar scraping
        resultado = scraper.extraer_todas_empresas()
        
        # Exportar resultados
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_salida = f"output/empresas_{timestamp}.json"
        resultado.to_json(archivo_salida)
        
        print(f"\n✅ Scraping completado exitosamente!")
        print(f"📊 Total empresas: {resultado.total_empresas}")
        print(f"❌ Errores: {resultado.errores}")
        print(f"⏱️  Tiempo total: {resultado.tiempo_total}")
        print(f"💾 Archivo generado: {archivo_salida}")
        
    except Exception as e:
        print(f"❌ Error en el scraping: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

