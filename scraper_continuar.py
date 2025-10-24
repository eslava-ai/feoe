"""
Script para continuar el scraping desde donde se quedó, usando GeckoDriver específico
"""
import os
import time
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Set

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from models import EmpresaCompleta, ScrapingResult


class SAOScraperContinuar:
    """Clase para continuar el scraping desde donde se quedó"""
    
    def __init__(self, headless: bool = False):
        """
        Inicializa el scraper
        
        Args:
            headless: Si True, ejecuta el navegador en modo headless
        """
        self.headless = headless
        self.driver = None
        self.wait = None
        self.errores = 0
        self.localidades_procesadas = set()
        self.archivo_progreso = "progreso_localidades.json"
        
        # Configurar logging
        self._setup_logging()
        
        # Cargar variables de entorno
        load_dotenv()
        
        # Verificar credenciales
        self.usuario = os.getenv('SAO_USUARIO')
        self.password = os.getenv('SAO_PASSWORD')
        
        if not self.usuario or not self.password:
            raise ValueError("Credenciales no encontradas en .env")
        
        # Cargar progreso previo
        self.cargar_progreso()
        
        # Configurar WebDriver
        self._setup_driver()
        
        # Realizar login
        if not self.login():
            raise Exception("No se pudo realizar el login")

    def _setup_logging(self):
        """Configura el sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scraper_continuar.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _setup_driver(self):
        """Configura el WebDriver usando una versión específica de GeckoDriver"""
        try:
            self.logger.info("Configurando Firefox WebDriver...")
            
            firefox_options = Options()
            if self.headless:
                firefox_options.add_argument("--headless")
            
            # Opciones para mayor estabilidad
            firefox_options.add_argument("--no-sandbox")
            firefox_options.add_argument("--disable-dev-shm-usage")
            firefox_options.add_argument("--disable-gpu")
            firefox_options.add_argument("--disable-web-security")
            firefox_options.add_argument("--disable-features=VizDisplayCompositor")
            firefox_options.add_argument("--window-size=1920,1080")
            
            # Configuraciones para evitar detección de automatización
            firefox_options.set_preference("dom.webdriver.enabled", False)
            firefox_options.set_preference("useAutomationExtension", False)
            firefox_options.set_preference("general.useragent.override", 
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0")
            
            # Usar GeckoDriver específico si está disponible
            geckodriver_path = None
            possible_paths = [
                r"C:\Users\veslava\.wdm\drivers\geckodriver\win64\v0.36.0\geckodriver.exe",
                r"C:\Users\veslava\.wdm\drivers\geckodriver\win64\v0.35.0\geckodriver.exe",
                r"C:\Users\veslava\.wdm\drivers\geckodriver\win64\v0.34.0\geckodriver.exe"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    geckodriver_path = path
                    self.logger.info(f"Usando GeckoDriver existente: {path}")
                    break
            
            if geckodriver_path:
                service = FirefoxService(executable_path=geckodriver_path)
            else:
                # Si no hay GeckoDriver específico, intentar descargar
                try:
                    from webdriver_manager.firefox import GeckoDriverManager
                    service = FirefoxService(GeckoDriverManager().install())
                    self.logger.info("GeckoDriver descargado automáticamente")
                except Exception as e:
                    self.logger.error(f"Error descargando GeckoDriver: {e}")
                    raise
            
            self.driver = webdriver.Firefox(service=service, options=firefox_options)
            
            # Configurar timeouts más largos
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, 20)
            
            # Ejecutar script para ocultar automatización
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info("WebDriver Firefox configurado correctamente")
            
        except Exception as e:
            self.logger.error(f"Error configurando WebDriver: {e}")
            raise

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
            time.sleep(3)
            
            # Buscar campos de login
            usuario_field = self.driver.find_element(By.NAME, "usuario")
            password_field = self.driver.find_element(By.NAME, "password")
            
            # Rellenar credenciales
            usuario_field.clear()
            usuario_field.send_keys(self.usuario)
            
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Enviar formulario
            submit_button = self.driver.find_element(By.XPATH, "//input[@type='submit']")
            submit_button.click()
            time.sleep(3)
            
            # Verificar si el login fue exitoso
            if "login" not in self.driver.current_url.lower():
                self.logger.info("Login exitoso")
                return True
            else:
                self.logger.error("Error en el login")
                return False
                
        except Exception as e:
            self.logger.error(f"Error durante el login: {e}")
            return False

    def obtener_localidades_disponibles(self) -> List[str]:
        """
        Obtiene la lista de localidades disponibles (cached o fresh)
        
        Returns:
            List[str]: Lista de localidades únicas
        """
        try:
            # Verificar si ya tenemos la lista guardada
            cache_file = "localidades_cache.json"
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        localidades = cache_data.get('localidades', [])
                        timestamp = cache_data.get('timestamp', '')
                        self.logger.info(f"Usando lista de localidades en caché ({len(localidades)} localidades, {timestamp})")
                        return localidades
                except Exception as e:
                    self.logger.warning(f"Error leyendo caché: {e}")
            
            # Si no hay caché, obtener la lista completa
            self.logger.info("Obteniendo lista de localidades de todas las páginas...")
            
            # Navegar a la página con ordenamiento por localidad
            listado_url = "https://foremp.edu.gva.es/index.php?op=4&subop=0&orden=localidad&sentido=asc"
            self.driver.get(listado_url)
            self.logger.info(f"Navegando a: {listado_url}")
            time.sleep(3)
            
            localidades = set()
            pagina_actual = 1
            total_empresas = 0
            
            while True:
                self.logger.info(f"Procesando página {pagina_actual}...")
                
                # Buscar tabla de empresas en la página actual
                tabla_empresas = self.driver.find_element(By.CSS_SELECTOR, "table")
                filas = tabla_empresas.find_elements(By.TAG_NAME, "tr")
                
                empresas_en_pagina = 0
                
                for i, fila in enumerate(filas[1:], 1):  # Saltar encabezado
                    try:
                        celdas = fila.find_elements(By.TAG_NAME, "td")
                        
                        if len(celdas) >= 7:  # Mínimo 7 columnas esperadas
                            # Extraer localidad de la columna 6 (índice 6)
                            localidad = celdas[6].text.strip() if len(celdas) > 6 else ""
                            
                            if localidad:
                                localidades.add(localidad)
                                empresas_en_pagina += 1
                                
                    except Exception as e:
                        self.logger.warning(f"Error procesando fila {i}: {e}")
                        continue
                
                total_empresas += empresas_en_pagina
                self.logger.info(f"Página {pagina_actual}: {empresas_en_pagina} empresas (Total: {total_empresas})")
                
                # Buscar enlace a siguiente página
                try:
                    # Buscar diferentes tipos de enlaces de paginación
                    siguiente_enlaces = self.driver.find_elements(By.XPATH, 
                        "//a[contains(text(), 'Siguiente') or contains(text(), '>') or contains(text(), '>>') or contains(@class, 'next')]")
                    
                    siguiente_enlace = None
                    for enlace in siguiente_enlaces:
                        if enlace.is_enabled() and enlace.is_displayed():
                            siguiente_enlace = enlace
                            break
                    
                    if siguiente_enlace:
                        siguiente_enlace.click()
                        time.sleep(3)
                        pagina_actual += 1
                    else:
                        self.logger.info("No hay más páginas disponibles")
                        break
                        
                except Exception as e:
                    self.logger.info(f"No se encontró enlace a siguiente página: {e}")
                    break
            
            localidades_lista = sorted(list(localidades))
            self.logger.info(f"Total localidades encontradas en {pagina_actual} páginas: {len(localidades_lista)}")
            self.logger.info(f"Total empresas encontradas: {total_empresas}")
            
            # Guardar en caché para futuras ejecuciones
            try:
                cache_data = {
                    'localidades': localidades_lista,
                    'timestamp': datetime.now().isoformat(),
                    'total_paginas': pagina_actual,
                    'total_empresas': total_empresas
                }
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Lista de localidades guardada en caché: {cache_file}")
            except Exception as e:
                self.logger.warning(f"Error guardando caché: {e}")
            
            return localidades_lista
            
        except Exception as e:
            self.logger.error(f"Error obteniendo localidades: {e}")
            return []

    def extraer_empresas_por_localidad(self, localidad: str) -> List[EmpresaCompleta]:
        """
        Extrae todas las empresas de una localidad específica
        
        Args:
            localidad: Nombre de la localidad
            
        Returns:
            List[EmpresaCompleta]: Lista de empresas de la localidad
        """
        try:
            self.logger.info(f"Extrayendo empresas de {localidad}...")
            
            # Navegar a la página con ordenamiento por localidad
            listado_url = "https://foremp.edu.gva.es/index.php?op=4&subop=0&orden=localidad&sentido=asc"
            self.driver.get(listado_url)
            time.sleep(3)
            
            # Buscar tabla de empresas
            tabla_empresas = self.driver.find_element(By.CSS_SELECTOR, "table")
            filas = tabla_empresas.find_elements(By.TAG_NAME, "tr")
            
            empresas = []
            
            for i, fila in enumerate(filas[1:], 1):  # Saltar encabezado
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    
                    if len(celdas) >= 7:  # Mínimo 7 columnas esperadas
                        # Extraer localidad de la columna 6 (índice 6)
                        localidad_empresa = celdas[6].text.strip() if len(celdas) > 6 else ""
                        
                        # Solo procesar empresas de la localidad específica
                        if localidad_empresa == localidad:
                            # Extraer id_empresa del enlace
                            enlace = fila.find_element(By.TAG_NAME, "a")
                            href = enlace.get_attribute("href")
                            id_empresa = re.search(r'idEmpresa=(\d+)', href)
                            id_empresa = id_empresa.group(1) if id_empresa else ""
                            
                            # Extraer nombre de la empresa
                            nombre = celdas[1].text.strip() if len(celdas) > 1 else ""
                            
                            # Crear empresa básica
                            empresa = EmpresaCompleta(
                                id_empresa=id_empresa,
                                nombre=nombre,
                                localidad=localidad
                            )
                            
                            empresas.append(empresa)
                            self.logger.info(f"Empresa {len(empresas)}: {id_empresa} - {nombre}")
                        
                except Exception as e:
                    self.logger.warning(f"Error procesando fila {i}: {e}")
                    self.errores += 1
                    continue
            
            self.logger.info(f"Empresas encontradas en {localidad}: {len(empresas)}")
            return empresas
            
        except Exception as e:
            self.logger.error(f"Error extrayendo empresas de {localidad}: {e}")
            return []

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
            time.sleep(2)
            
            # Extraer datos detallados
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
            
            # Delay entre peticiones (más largo para evitar saturar el servidor)
            time.sleep(2.0)
            
            return empresa
            
        except Exception as e:
            self.logger.error(f"Error navegando a detalle de empresa {empresa.id_empresa}: {e}")
            return empresa

    def _extraer_campo(self, nombre_campo: str) -> str:
        """
        Extrae un campo específico de la página de detalle
        
        Args:
            nombre_campo: Nombre del campo a extraer
            
        Returns:
            str: Valor del campo
        """
        try:
            # Buscar tabla de información
            tabla_info = self.driver.find_element(By.CSS_SELECTOR, "table.infoUsuario.infoEmpresa")
            filas = tabla_info.find_elements(By.TAG_NAME, "tr")
            
            if len(filas) >= 2:
                headers = filas[0].find_elements(By.TAG_NAME, "th")
                valores = filas[1].find_elements(By.TAG_NAME, "td")
                
                for i, header in enumerate(headers):
                    if header.text.strip() == nombre_campo and i < len(valores):
                        return valores[i].text.strip()
            
            return ""
            
        except Exception as e:
            self.logger.warning(f"Error extrayendo campo {nombre_campo}: {e}")
            return ""

    def procesar_localidad(self, localidad: str) -> bool:
        """
        Procesa una localidad específica
        
        Args:
            localidad: Nombre de la localidad
            
        Returns:
            bool: True si se procesó exitosamente
        """
        try:
            self.logger.info(f"=== Procesando localidad: {localidad} ===")
            
            # Extraer empresas de la localidad
            empresas = self.extraer_empresas_por_localidad(localidad)
            
            if not empresas:
                self.logger.info(f"No hay empresas en {localidad} - localidad vacía (normal)")
                # Marcar como procesada aunque esté vacía
                self.guardar_progreso(localidad)
                return True
            
            # Procesar cada empresa
            empresas_completas = []
            for i, empresa in enumerate(empresas, 1):
                try:
                    self.logger.info(f"Procesando empresa {i}/{len(empresas)}: {empresa.id_empresa}")
                    
                    # Extraer detalles de la empresa
                    empresa_completa = self.extraer_detalle_empresa(empresa)
                    empresas_completas.append(empresa_completa)
                    
                except Exception as e:
                    self.logger.error(f"Error procesando empresa {empresa.id_empresa}: {e}")
                    self.errores += 1
                    continue
            
            # Guardar archivo por localidad
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo_salida = f"output/empresas_{localidad}_{timestamp}.json"
            
            resultado = ScrapingResult(
                empresas=empresas_completas,
                timestamp=datetime.now().isoformat(),
                total_empresas=len(empresas_completas),
                errores=self.errores,
                tiempo_total=None
            )
            
            resultado.to_json(archivo_salida)
            
            self.logger.info(f"Localidad {localidad} completada: {len(empresas_completas)} empresas guardadas en {archivo_salida}")
            
            # Guardar progreso
            self.guardar_progreso(localidad)
            
            self.logger.info(f"Localidad {localidad} completada exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error procesando localidad {localidad}: {e}")
            return False

    def cargar_progreso(self):
        """Carga el progreso previo desde el archivo JSON"""
        try:
            if os.path.exists(self.archivo_progreso):
                with open(self.archivo_progreso, 'r', encoding='utf-8') as f:
                    progreso = json.load(f)
                    self.localidades_procesadas = set(progreso.get('localidades_procesadas', []))
                    self.logger.info(f"Progreso cargado: {len(self.localidades_procesadas)} localidades ya procesadas")
            else:
                self.logger.info("No hay progreso previo")
        except Exception as e:
            self.logger.warning(f"Error cargando progreso: {e}")

    def guardar_progreso(self, localidad: str):
        """Guarda el progreso actual en el archivo JSON"""
        try:
            self.localidades_procesadas.add(localidad)
            
            progreso = {
                "localidades_procesadas": list(self.localidades_procesadas),
                "ultima_actualizacion": datetime.now().isoformat()
            }
            
            with open(self.archivo_progreso, 'w', encoding='utf-8') as f:
                json.dump(progreso, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Progreso guardado: {localidad} añadida")
            
        except Exception as e:
            self.logger.error(f"Error guardando progreso: {e}")

    def procesar_localidades(self, max_localidades: Optional[int] = None):
        """
        Procesa todas las localidades pendientes
        
        Args:
            max_localidades: Número máximo de localidades a procesar (None para todas)
        """
        try:
            self.logger.info("Obteniendo lista de localidades...")
            
            # Obtener todas las localidades
            localidades = self.obtener_localidades_disponibles()
            
            if not localidades:
                self.logger.error("No se encontraron localidades")
                return
            
            # Filtrar localidades ya procesadas
            localidades_pendientes = [loc for loc in localidades if loc not in self.localidades_procesadas]
            
            self.logger.info(f"Localidades totales: {len(localidades)}")
            self.logger.info(f"Localidades ya procesadas: {len(self.localidades_procesadas)}")
            self.logger.info(f"Localidades pendientes: {len(localidades_pendientes)}")
            
            # Procesar localidades pendientes
            if max_localidades is None:
                localidades_a_procesar = localidades_pendientes
            else:
                localidades_a_procesar = localidades_pendientes[:max_localidades]
            
            self.logger.info(f"Procesando {len(localidades_a_procesar)} localidades: {localidades_a_procesar}")
            
            # Procesar cada localidad
            for i, localidad in enumerate(localidades_a_procesar, 1):
                self.logger.info(f"\n--- Procesando localidad {i}/{len(localidades_a_procesar)}: {localidad} ---")
                
                try:
                    if self.procesar_localidad(localidad):
                        self.logger.info(f"Localidad {localidad} procesada exitosamente")
                    else:
                        self.logger.error(f"Error procesando localidad {localidad}")
                        
                except Exception as e:
                    self.logger.error(f"Error procesando localidad {localidad}: {e}")
                    continue
            
            self.logger.info("Procesamiento completado!")
            self.logger.info(f"Localidades procesadas: {len(self.localidades_procesadas)}")
            self.logger.info(f"Errores totales: {self.errores}")
            
        except Exception as e:
            self.logger.error(f"Error en el procesamiento: {e}")

    def cerrar(self):
        """Cierra el navegador"""
        if self.driver:
            self.driver.quit()
            self.logger.info("Navegador cerrado")


def main():
    """Función principal"""
    scraper = None
    try:
        # Crear directorio de salida
        Path("output").mkdir(exist_ok=True)
        
        # Inicializar scraper
        scraper = SAOScraperContinuar(headless=False)  # Cambiar a True para ejecución sin interfaz
        
        # Procesar localidades pendientes (máximo 5 para prueba)
        scraper.procesar_localidades(max_localidades=5)
        
    except Exception as e:
        print(f"❌ Error en el scraping: {e}")
        return 1
    finally:
        if scraper:
            scraper.cerrar()
    
    return 0


if __name__ == "__main__":
    exit(main())
