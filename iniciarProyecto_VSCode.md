# Cómo iniciar el proyecto GH Diseños en Visual Studio Code

## Requisitos
- [Visual Studio Code](https://code.visualstudio.com/)
- [Python 3.11.5+](https://www.python.org/downloads/) (marca "Add Python to PATH" durante la instalación)
- [Git](https://git-scm.com/download/win) (opcional si descargas el ZIP)

## Paso 1: Obtener el proyecto
**Opción A: Clonar con Git (recomendado)**
1. Abre VS Code
2. Pulsa Ctrl+Shift+P → escribe Git: Clone → Enter
3. Pega esta URL: https://github.com/GregorioZamora/GH-Corps.git
4. Selecciona la carpeta donde quieras guardarlo

**Opción B: Descargar ZIP**
1. Ve a [github.com/GregorioZamora/GH-Corps](https://github.com/GregorioZamora/GH-Corps)
2. Code > Download ZIP → descomprime en tu PC
3. Abre esa carpeta con VS Code (Archivo > Abrir carpeta...)

## Paso 2: Abrir la carpeta en VS Code
Abre VS Code → Archivo > Abrir carpeta... → selecciona GH-Corps.

## Paso 3: Crear y activar el entorno virtual
1. Abre la Terminal de VS Code (Ctrl+` )
2. Escribe esto y pulsa Enter:
`powershell
py -m venv venv
`
3. Activa el entorno virtual:
`powershell
.\venv\Scripts\Activate.ps1
`
Si te sale un aviso sobre ejecución de scripts, lee el mensaje: normalmente basta con aceptar. Si no funciona, prueba:
`powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\venv\Scripts\Activate.ps1
`

## Paso 4: Instalar dependencias
En la misma terminal (con (venv) al inicio):
`powershell
pip install -r requirements.txt
`

## Paso 5: Configurar .env
Copia el archivo .env.example y renómbralo a .env.
- En VS Code: botón derecho sobre .env.example → Copiar → botón derecho en la carpeta → Pegar → renombra a .env
- O desde terminal:
`powershell
copy .env.example .env
`

## Paso 6: Iniciar el proyecto
Con el entorno virtual activo:
`powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
`

## Paso 7: Verlo en web
Cuando aparezca Application startup complete abre este enlace:
[http://127.0.0.1:8000](http://127.0.0.1:8000)

## Para parar
Pulsa Ctrl+C en la terminal.

## Datos de prueba
- Admin: infoghdisenos@gmail.com / dmin1234

## Solución rápida si falla
Si ves errores raros, cierra VS Code, vuelve a abrir la carpeta, activa env e instala dependencias otra vez.