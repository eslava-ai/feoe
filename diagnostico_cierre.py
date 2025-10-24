"""
Script de diagnóstico para identificar causas del cierre del navegador
"""
import os
import time
import traceback
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def diagnostico_completo():
    """Realiza un diagnóstico completo del sistema"""
    print("=== DIAGNÓSTICO DE CIERRE DEL NAVEGADOR ===\n")
    
    try:
        # 1. Verificar credenciales
        print("1. Verificando credenciales...")
        load_dotenv()
        usuario = os.getenv('SAO_USUARIO')
        password = os.getenv('SAO_PASSWORD')
        
        if not usuario or not password:
            print("   ❌ Credenciales no encontradas en .env")
            return
        else:
            print(f"   ✅ Credenciales encontradas: {usuario[:3]}***")
        
        # 2. Verificar WebDriver
        print("\n2. Verificando WebDriver...")
        try:
            service = FirefoxService(GeckoDriverManager().install())
            print("   ✅ GeckoDriver instalado correctamente")
        except Exception as e:
            print(f"   ❌ Error con GeckoDriver: {e}")
            return
        
        # 3. Configurar navegador con opciones de diagnóstico
        print("\n3. Configurando navegador...")
        firefox_options = webdriver.FirefoxOptions()
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")
        firefox_options.add_argument("--disable-gpu")
        firefox_options.add_argument("--window-size=1920,1080")
        
        # Habilitar logging detallado
        firefox_options.set_preference("browser.dom.window.dump.enabled", True)
        firefox_options.set_preference("devtools.console.stdout.chrome", True)
        
        driver = webdriver.Firefox(service=service, options=firefox_options)
        wait = WebDriverWait(driver, 15)
        
        print("   ✅ Navegador configurado")
        
        # 4. Probar navegación básica
        print("\n4. Probando navegación básica...")
        try:
            driver.get("https://foremp.edu.gva.es/index.php?op=4&subop=0")
            time.sleep(3)
            print(f"   ✅ Página cargada: {driver.current_url}")
        except Exception as e:
            print(f"   ❌ Error cargando página: {e}")
            return
        
        # 5. Probar login
        print("\n5. Probando login...")
        try:
            usuario_field = driver.find_element(By.NAME, "usuario")
            password_field = driver.find_element(By.NAME, "password")
            
            usuario_field.clear()
            usuario_field.send_keys(usuario)
            
            password_field.clear()
            password_field.send_keys(password)
            
            submit_button = driver.find_element(By.XPATH, "//input[@type='submit']")
            submit_button.click()
            time.sleep(5)
            
            print(f"   ✅ Login realizado: {driver.current_url}")
        except Exception as e:
            print(f"   ❌ Error en login: {e}")
            return
        
        # 6. Probar navegación a listado
        print("\n6. Probando navegación a listado...")
        try:
            listado_url = "https://foremp.edu.gva.es/index.php?op=4&subop=0&orden=localidad&sentido=asc"
            driver.get(listado_url)
            time.sleep(3)
            print(f"   ✅ Listado cargado: {driver.current_url}")
        except Exception as e:
            print(f"   ❌ Error cargando listado: {e}")
            return
        
        # 7. Probar extracción de datos
        print("\n7. Probando extracción de datos...")
        try:
            tabla_empresas = driver.find_element(By.CSS_SELECTOR, "table")
            filas = tabla_empresas.find_elements(By.TAG_NAME, "tr")
            print(f"   ✅ Tabla encontrada: {len(filas)} filas")
            
            # Probar extracción de primera empresa
            if len(filas) > 1:
                primera_fila = filas[1]
                celdas = primera_fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) >= 2:
                    enlace = primera_fila.find_element(By.TAG_NAME, "a")
                    href = enlace.get_attribute("href")
                    print(f"   ✅ Primera empresa: {href}")
        except Exception as e:
            print(f"   ❌ Error extrayendo datos: {e}")
            return
        
        # 8. Probar navegación a detalle
        print("\n8. Probando navegación a detalle...")
        try:
            if len(filas) > 1:
                primera_fila = filas[1]
                enlace = primera_fila.find_element(By.TAG_NAME, "a")
                href = enlace.get_attribute("href")
                
                print(f"   Navegando a: {href}")
                driver.get(href)
                time.sleep(3)
                print(f"   ✅ Página de detalle cargada: {driver.current_url}")
        except Exception as e:
            print(f"   ❌ Error navegando a detalle: {e}")
            return
        
        # 9. Probar extracción de campos
        print("\n9. Probando extracción de campos...")
        try:
            # Buscar tabla de información
            tabla_info = driver.find_element(By.CSS_SELECTOR, "table.infoUsuario.infoEmpresa")
            filas_info = tabla_info.find_elements(By.TAG_NAME, "tr")
            
            if len(filas_info) >= 2:
                headers = filas_info[0].find_elements(By.TAG_NAME, "th")
                valores = filas_info[1].find_elements(By.TAG_NAME, "td")
                
                print(f"   ✅ Tabla de información: {len(headers)} campos")
                
                # Mostrar algunos campos
                for i, (header, valor) in enumerate(zip(headers[:5], valores[:5])):
                    print(f"     {header.text}: {valor.text}")
        except Exception as e:
            print(f"   ❌ Error extrayendo campos: {e}")
            return
        
        # 10. Probar navegación de vuelta
        print("\n10. Probando navegación de vuelta...")
        try:
            driver.get("https://foremp.edu.gva.es/index.php?op=4&subop=0&orden=localidad&sentido=asc")
            time.sleep(3)
            print(f"   ✅ Navegación de vuelta exitosa: {driver.current_url}")
        except Exception as e:
            print(f"   ❌ Error en navegación de vuelta: {e}")
            return
        
        print("\n=== DIAGNÓSTICO COMPLETADO ===")
        print("✅ Todas las pruebas pasaron correctamente")
        print("✅ El navegador debería funcionar sin problemas")
        print("✅ Si se cierra, puede ser por:")
        print("   - Timeout de sesión del servidor")
        print("   - Detección de automatización")
        print("   - Límites de peticiones")
        print("   - Problemas de memoria")
        
        print("\nCerrando navegador...")
        driver.quit()
        
    except Exception as e:
        print(f"\n❌ Error crítico en diagnóstico: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    diagnostico_completo()
