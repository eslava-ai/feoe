"""
Script de monitoreo para detectar cierres inesperados del navegador
"""
import os
import time
import psutil
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def monitorear_navegador():
    """Monitorea el estado del navegador durante el scraping"""
    try:
        # Cargar credenciales
        load_dotenv()
        usuario = os.getenv('SAO_USUARIO')
        password = os.getenv('SAO_PASSWORD')
        
        if not usuario or not password:
            print("Error: Credenciales no encontradas en .env")
            return
        
        print("Configurando Firefox...")
        
        # Configurar Firefox
        firefox_options = webdriver.FirefoxOptions()
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")
        
        service = FirefoxService(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=firefox_options)
        wait = WebDriverWait(driver, 10)
        
        print("Realizando login...")
        
        # Login
        login_url = "https://foremp.edu.gva.es/index.php?op=4&subop=0"
        driver.get(login_url)
        time.sleep(3)
        
        usuario_field = driver.find_element(By.NAME, "usuario")
        password_field = driver.find_element(By.NAME, "password")
        
        usuario_field.clear()
        usuario_field.send_keys(usuario)
        
        password_field.clear()
        password_field.send_keys(password)
        
        submit_button = driver.find_element(By.XPATH, "//input[@type='submit']")
        submit_button.click()
        time.sleep(3)
        
        print("Login exitoso")
        
        # Monitorear durante 5 minutos
        print("Monitoreando navegador durante 5 minutos...")
        print("Presiona Ctrl+C para detener")
        
        for i in range(300):  # 5 minutos
            try:
                # Verificar si el driver sigue activo
                current_url = driver.current_url
                print(f"Minuto {i//60}:{i%60:02d} - URL: {current_url}")
                
                # Verificar procesos de Firefox
                firefox_processes = [p for p in psutil.process_iter(['pid', 'name']) if 'firefox' in p.info['name'].lower()]
                print(f"  Procesos Firefox activos: {len(firefox_processes)}")
                
                # Navegar a una página cada 30 segundos para mantener la sesión
                if i % 30 == 0 and i > 0:
                    print("  Navegando para mantener sesión...")
                    driver.get("https://foremp.edu.gva.es/index.php?op=4&subop=0")
                    time.sleep(2)
                
                time.sleep(1)
                
            except Exception as e:
                print(f"Error en monitoreo: {e}")
                break
        
        print("Cerrando navegador...")
        driver.quit()
        
    except KeyboardInterrupt:
        print("\nMonitoreo interrumpido por el usuario")
        try:
            driver.quit()
        except:
            pass
    except Exception as e:
        print(f"Error general: {e}")

if __name__ == "__main__":
    monitorear_navegador()
