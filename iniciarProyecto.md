# CÃ³mo iniciar el proyecto GH DiseÃ±os

## Requisitos
- Python 3.11.5 o superior
- pip

## Pasos para iniciar

1. **Clonar el repositorio** (si no lo tienes ya)
```bash
git clone https://github.com/GregorioZamora/GH-Corps.git
cd GH-Corps
```

2. **Crear entorno virtual** (recomendado)
```bash
python -m venv venv
```

3. **Activar entorno virtual**
- Windows (PowerShell):
```powershell
.\venv\Scripts\Activate.ps1
```
- Windows (CMD):
```cmd
venv\Scripts\activate.bat
```
- Linux/Mac:
```bash
source venv/bin/activate
```

4. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

5. **Configurar variables de entorno**
Copia `.env.example` a `.env` y ajusta los valores si lo necesitas (la app funciona con valores por defecto para desarrollo):
```bash
cp .env.example .env  # Linux/Mac
copy .env.example .env  # Windows CMD
```

6. **Iniciar servidor de desarrollo**
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

7. **Abrir en el navegador**
Ve a [http://127.0.0.1:8000](http://127.0.0.1:8000)


## Tests
Para ejecutar smoke + i18n desde PowerShell (test):
```powershell
$env:PYTHONPATH="."; $env:DATABASE_URL="sqlite+aiosqlite:///./gh_corps_test.db"; Remove-Item gh_corps_test.db -ErrorAction SilentlyContinue; python tests/test_smoke.py; python tests/test_i18n.py
```

## Notas
- El directorio `app/uploads/` mantiene `.gitkeep` (los archivos subidos se ignoran en git).
- Para detener el servidor pulsa `Ctrl+C`.
- No uses `--reload` en algunos entornos de Windows (puede duplicar procesos). 

**Listo. Con esto puedes levantar el proyecto localmente y verlo en web.**
