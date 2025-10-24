# Script de Extracción de Empresas FCT

Este script automatiza la extracción de datos de empresas del sistema SAÓ FCT de la Generalitat Valenciana para gestionar las prácticas de alumnos.

## 🚀 Características

- ✅ Login automático con credenciales seguras
- ✅ Extracción del listado principal de empresas
- ✅ Obtención de datos detallados de cada empresa
- ✅ Exportación a JSON con timestamp
- ✅ Logging completo y manejo de errores
- ✅ Screenshots automáticos en caso de error
- ✅ Configuración headless opcional

## 📋 Datos Extraídos

### Del listado principal:
- ID de empresa
- Fecha de registro
- Último acceso

### De cada página de detalle:
- CIF
- Nombre
- Dirección
- Provincia
- Localidad
- Código postal
- Teléfono
- Fax
- Actividad
- Nombre del gerente
- NIF del gerente
- Email
- Tipo

## 🛠️ Instalación

### 1. Clonar el repositorio
```bash
git clone <url-del-repositorio>
cd feoe
```

### 2. Crear entorno virtual
```bash
python -m venv venv
```

### 3. Activar entorno virtual

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 5. Configurar credenciales
```bash
# Copiar plantilla de credenciales
copy .env.example .env

# Editar .env con tus credenciales reales
notepad .env
```

Rellena el archivo `.env` con tus credenciales:
```
SAO_USUARIO=tu_usuario_aqui
SAO_PASSWORD=tu_contraseña_aqui
```

## 🚀 Uso

### Ejecución básica
```bash
python scraper.py
```

### Ejecución en modo headless (sin interfaz gráfica)
Edita `scraper.py` y cambia:
```python
scraper = SAOScraper(headless=True)
```

## 📁 Estructura del Proyecto

```
feoe/
├── .env                    # Credenciales (NO se sube a Git)
├── .env.example           # Plantilla de credenciales
├── .gitignore             # Archivos ignorados por Git
├── requirements.txt       # Dependencias Python
├── models.py              # Modelos de datos
├── scraper.py             # Script principal
├── README.md              # Este archivo
├── output/                # Archivos JSON generados
│   └── empresas_YYYYMMDD_HHMMSS.json
└── scraper.log            # Log de ejecución
```

## 📊 Archivos de Salida

El script genera archivos JSON con la siguiente estructura:

```json
{
  "metadata": {
    "timestamp": "2024-01-15T10:30:00",
    "total_empresas": 150,
    "errores": 2,
    "tiempo_total": "0:05:30"
  },
  "empresas": [
    {
      "id_empresa": "67331",
      "registrado": "2023-01-15",
      "ultimo_acceso": "2024-01-10",
      "cif": "A12345678",
      "nombre": "Empresa Ejemplo S.L.",
      "direccion": "Calle Principal 123",
      "provincia": "Valencia",
      "localidad": "Valencia",
      "cp": "46001",
      "telefono": "963123456",
      "fax": "963123457",
      "actividad": "Tecnología",
      "nombre_gerente": "Juan Pérez",
      "nif_gerente": "12345678A",
      "email": "contacto@empresa.com",
      "tipo": "PYME"
    }
  ]
}
```

## ⚙️ Configuración Avanzada

### Ajustar selectores HTML
Tras la primera ejecución, es posible que necesites ajustar los selectores en `scraper.py`:

1. **Login**: Ajusta los nombres de los campos de usuario y contraseña
2. **Listado**: Modifica el selector de la tabla de empresas
3. **Detalles**: Ajusta los XPath para extraer campos específicos

### Modificar delays
```python
# En scraper.py, línea ~200
time.sleep(0.5)  # Cambiar delay entre peticiones
```

### Configurar timeouts
```python
# En scraper.py, línea ~50
self.wait = WebDriverWait(self.driver, 10)  # Cambiar timeout
```

## 🔒 Seguridad

- ✅ Las credenciales se almacenan en `.env` (no se sube a Git)
- ✅ El archivo `.env` está en `.gitignore`
- ✅ Usa variables de entorno para credenciales
- ✅ Logs no contienen información sensible

## 🐛 Solución de Problemas

### Error: "Credenciales no encontradas"
- Verifica que el archivo `.env` existe
- Comprueba que las variables `SAO_USUARIO` y `SAO_PASSWORD` están definidas

### Error: "ChromeDriver no encontrado"
- El script descarga automáticamente ChromeDriver
- Verifica tu conexión a internet

### Error: "Elemento no encontrado"
- Los selectores HTML pueden haber cambiado
- Revisa `scraper.log` para más detalles
- Ajusta los selectores en `scraper.py`

### Error de login
- Verifica que las credenciales son correctas
- Comprueba que el sistema SAÓ FCT está disponible
- Revisa si hay captcha o verificación adicional

## 📝 Logs

El script genera logs en `scraper.log` con información detallada:
- Progreso de extracción
- Errores específicos
- Tiempo de ejecución
- Screenshots automáticos en caso de error

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Añadir nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## ⚠️ Aviso Legal

Este script es para uso educativo y de gestión interna. Asegúrate de cumplir con:
- Términos de uso del sistema SAÓ FCT
- Políticas de la Generalitat Valenciana
- Legislación de protección de datos (RGPD)

## 📞 Soporte

Si encuentras problemas:
1. Revisa los logs en `scraper.log`
2. Verifica la configuración de credenciales
3. Comprueba que el sistema SAÓ FCT está disponible
4. Abre un issue en el repositorio con detalles del error

