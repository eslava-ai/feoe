"""
Script principal para extraer datos de empresas del sistema SAÓ FCT por localidades
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
from webdriver_manager.firefox import GeckoDriverManager

from models import EmpresaCompleta, ScrapingResult


class SAOScraperLocalidades:
    """Clase principal para el scraping del sistema SAÓ FCT por localidades"""
    
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
            raise ValueError("Credenciales no encontradas en .env. Verifica SAO_USUARIO y SAO_PASSWORD")

    def _setup_logging(self):
        """Configura el sistema de logging"""
        # Configurar handler para archivo con UTF-8
        file_handler = logging.FileHandler('scraper_localidades.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Configurar handler para consola sin emojis
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formato sin emojis para evitar problemas de codificación
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Configurar logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _setup_driver(self):
        """Configura el WebDriver (Firefox por defecto)"""
        try:
            from selenium.webdriver.firefox.service import Service as FirefoxService
            from webdriver_manager.firefox import GeckoDriverManager
            
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
            
            service = FirefoxService(GeckoDriverManager().install())
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
            
            # Esperar a que cargue la página
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
            
            # Localizar campos de usuario y contraseña
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
            
            # Esperar a que cargue la página principal
            time.sleep(3)
            
            # Verificar si el login fue exitoso
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

    def obtener_localidades(self) -> List[str]:
        """
        Obtiene la lista de todas las localidades disponibles
        
        Returns:
            List[str]: Lista de localidades únicas
        """
        try:
            self.logger.info("Obteniendo lista de localidades...")
            
            # Navegar a la página con ordenamiento por localidad
            listado_url = "https://foremp.edu.gva.es/index.php?op=4&subop=0&orden=localidad&sentido=asc"
            self.driver.get(listado_url)
            self.logger.info(f"Navegando a: {listado_url}")
            
            # Esperar a que cargue la página
            time.sleep(3)
            
            # Buscar tabla de empresas
            tabla_empresas = self.driver.find_element(By.CSS_SELECTOR, "table")
            filas = tabla_empresas.find_elements(By.TAG_NAME, "tr")
            
            localidades = set()
            
            for i, fila in enumerate(filas[1:], 1):  # Saltar encabezado
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    
                    if len(celdas) >= 7:  # Mínimo 7 columnas esperadas
                        # Extraer localidad de la columna 6 (índice 6)
                        localidad = celdas[6].text.strip() if len(celdas) > 6 else ""
                        
                        if localidad and localidad not in localidades:
                            localidades.add(localidad)
                            self.logger.info(f"Localidad encontrada: {localidad}")
                            
                except Exception as e:
                    self.logger.warning(f"Error procesando fila {i}: {e}")
                    continue
            
            localidades_lista = sorted(list(localidades))
            self.logger.info(f"Total localidades encontradas: {len(localidades_lista)}")
            return localidades_lista
            
        except Exception as e:
            self.logger.error(f"Error obteniendo localidades: {e}")
            return []

    def cargar_progreso(self) -> Set[str]:
        """
        Carga el progreso de localidades ya procesadas
        
        Returns:
            Set[str]: Conjunto de localidades ya procesadas
        """
        if os.path.exists(self.archivo_progreso):
            try:
                with open(self.archivo_progreso, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.localidades_procesadas = set(data.get('localidades_procesadas', []))
                    self.logger.info(f"Progreso cargado: {len(self.localidades_procesadas)} localidades ya procesadas")
            except Exception as e:
                self.logger.warning(f"Error cargando progreso: {e}")
                self.localidades_procesadas = set()
        else:
            self.localidades_procesadas = set()
        
        return self.localidades_procesadas

    def guardar_progreso(self, localidad: str):
        """
        Guarda el progreso de localidades procesadas
        
        Args:
            localidad: Localidad que se acaba de procesar
        """
        self.localidades_procesadas.add(localidad)
        
        try:
            data = {
                'localidades_procesadas': list(self.localidades_procesadas),
                'ultima_actualizacion': datetime.now().isoformat()
            }
            
            with open(self.archivo_progreso, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Progreso guardado: {localidad} añadida")
            
        except Exception as e:
            self.logger.error(f"Error guardando progreso: {e}")

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

    def verificar_sesion_activa(self) -> bool:
        """
        Verifica si la sesión sigue activa
        
        Returns:
            bool: True si la sesión está activa, False si no
        """
        try:
            # Verificar si estamos en la página de login
            current_url = self.driver.current_url
            if "login" in current_url.lower() or "op=4&subop=0" in current_url:
                return False
            
            # Verificar si hay elementos de la página principal
            try:
                # Buscar algún elemento que indique que estamos logueados
                self.driver.find_element(By.CSS_SELECTOR, "table")
                return True
            except:
                return False
                
        except Exception as e:
            self.logger.warning(f"Error verificando sesión: {e}")
            return False

    def reconectar_si_es_necesario(self) -> bool:
        """
        Reconoce si la sesión se ha perdido
        
        Returns:
            bool: True si se reconectó exitosamente
        """
        if not self.verificar_sesion_activa():
            self.logger.warning("Sesión perdida, intentando reconectar...")
            return self.login()
        return True

    def extraer_detalle_empresa(self, empresa: EmpresaCompleta) -> EmpresaCompleta:
        """
        Extrae los datos detallados de una empresa
        
        Args:
            empresa: Objeto EmpresaCompleta con datos básicos
            
        Returns:
            EmpresaCompleta: Empresa con datos completos
        """
        try:
            # Verificar sesión antes de continuar
            if not self.reconectar_si_es_necesario():
                self.logger.error("No se pudo reconectar, saltando empresa")
                return empresa
            
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

    def procesar_localidad(self, localidad: str) -> bool:
        """
        Procesa una localidad completa: extrae empresas y sus detalles
        
        Args:
            localidad: Nombre de la localidad a procesar
            
        Returns:
            bool: True si el procesamiento fue exitoso
        """
        try:
            self.logger.info(f"=== Procesando localidad: {localidad} ===")
            
            # Extraer empresas de la localidad
            empresas = self.extraer_empresas_por_localidad(localidad)
            
            if not empresas:
                self.logger.warning(f"No se encontraron empresas en {localidad}")
                return False
            
            # Extraer detalles de cada empresa
            empresas_completas = []
            for i, empresa in enumerate(empresas, 1):
                self.logger.info(f"Procesando empresa {i}/{len(empresas)}: {empresa.id_empresa}")
                empresa_completa = self.extraer_detalle_empresa(empresa)
                empresas_completas.append(empresa_completa)
            
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
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error procesando localidad {localidad}: {e}")
            return False

    def procesar_localidades(self, max_localidades: int = 4) -> None:
        """
        Procesa las localidades disponibles
        
        Args:
            max_localidades: Número máximo de localidades a procesar (para pruebas)
        """
        inicio = datetime.now()
        
        try:
            # Configurar driver
            self._setup_driver()
            
            # Login
            if not self.login():
                raise Exception("Error en el login")
            
            # Cargar progreso previo
            self.cargar_progreso()
            
            # Obtener lista de localidades
            localidades = self.obtener_localidades()
            
            if not localidades:
                raise Exception("No se encontraron localidades")
            
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
                
                if self.procesar_localidad(localidad):
                    self.logger.info(f"Localidad {localidad} completada exitosamente")
                else:
                    self.logger.error(f"Error procesando localidad {localidad}")
            
            # Calcular tiempo total
            fin = datetime.now()
            tiempo_total = str(fin - inicio)
            
            self.logger.info(f"Procesamiento completado!")
            self.logger.info(f"Tiempo total: {tiempo_total}")
            self.logger.info(f"Localidades procesadas: {len(localidades_a_procesar)}")
            self.logger.info(f"Errores totales: {self.errores}")
            
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
        scraper = SAOScraperLocalidades(headless=False)  # Cambiar a True para ejecución sin interfaz
        
        # Ejecutar scraping (procesar todas las localidades)
        scraper.procesar_localidades(max_localidades=None)
        
    except Exception as e:
        print(f"❌ Error en el scraping: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
