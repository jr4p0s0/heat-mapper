#!/usr/bin/env python3
"""
Script de Instalación para WiFi Heatmap Generator Pro v7
Detecta el sistema operativo e instala las dependencias necesarias
"""

import subprocess
import sys
import platform
import os

def run_command(command, description, check=True):
    """Ejecuta un comando y maneja errores"""
    print(f"🔄 {description}...")
    try:
        if isinstance(command, str):
            result = subprocess.run(command, shell=True, check=check, 
                                  capture_output=True, text=True)
        else:
            result = subprocess.run(command, check=check, 
                                  capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {description} - Completado")
            return True
        else:
            print(f"⚠️  {description} - Advertencia: {result.stderr}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Error: {e}")
        return False
    except FileNotFoundError:
        print(f"⚠️  {description} - Comando no encontrado")
        return False

def check_python_version():
    """Verifica la versión de Python"""
    version = sys.version_info
    print(f"🐍 Python {version.major}.{version.minor}.{version.micro} detectado")
    
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("❌ Se requiere Python 3.7 o superior")
        return False
    
    print("✅ Versión de Python compatible")
    return True

def install_python_dependencies():
    """Instala las dependencias de Python"""
    dependencies = [
        "matplotlib",
        "numpy", 
        "scipy",
        "pillow"
    ]
    
    print("\n📦 Instalando dependencias de Python...")
    
    for dep in dependencies:
        success = run_command(
            [sys.executable, "-m", "pip", "install", dep],
            f"Instalando {dep}",
            check=False
        )
        
        if not success:
            print(f"⚠️  No se pudo instalar {dep}, intentando con --user")
            run_command(
                [sys.executable, "-m", "pip", "install", "--user", dep],
                f"Instalando {dep} (usuario)",
                check=False
            )

def install_windows_dependencies():
    """Instala dependencias específicas de Windows"""
    print("\n🪟 Configuración para Windows...")
    
    # netsh y wmic ya están incluidos en Windows
    print("✅ netsh y wmic ya están disponibles en Windows")
    
    # Intentar instalar iperf3 con winget
    if run_command("winget --version", "Verificando winget", check=False):
	# Instalar iperf3 desde winget de forma silenciosa
	subprocess.run([
    		"winget", "install", "iperf3",
    		"--silent",
		"--accept-package-agreements",
		"--accept-source-agreements"
	], check=True)
    else:
        print("⚠️  winget no disponible. Instala iperf3 manualmente desde: https://iperf.fr/")

def install_linux_dependencies():
    """Instala dependencias específicas de Linux"""
    print("\n🐧 Configuración para Linux...")
    
    # Detectar distribución
    try:
        with open("/etc/os-release", "r") as f:
            os_info = f.read().lower()
    except:
        os_info = ""
    
    if "ubuntu" in os_info or "debian" in os_info:
        print("📋 Sistema Debian/Ubuntu detectado")
        run_command("sudo apt update", "Actualizando repositorios", check=False)
        run_command("sudo apt install -y wireless-tools iw network-manager", 
                   "Instalando herramientas WiFi", check=False)
        run_command("sudo apt-get install -y iperf3", "Instalando iperf3 (opcional)", check=False)
        
    elif "fedora" in os_info or "rhel" in os_info or "centos" in os_info:
        print("📋 Sistema RedHat/Fedora detectado")
        # Intentar con dnf primero, luego yum
        if not run_command("sudo dnf install -y wireless-tools iw NetworkManager", 
                          "Instalando herramientas WiFi (dnf)", check=False):
            run_command("sudo yum install -y wireless-tools iw NetworkManager", 
                       "Instalando herramientas WiFi (yum)", check=False)
        
        if not run_command("sudo dnf install -y iperf3", "Instalando iperf3 (dnf)", check=False):
            run_command("sudo yum install -y iperf3", "Instalando iperf3 (yum)", check=False)
            
    elif "arch" in os_info:
        print("📋 Sistema Arch Linux detectado")
        run_command("sudo pacman -Sy --noconfirm wireless_tools iw networkmanager", 
                   "Instalando herramientas WiFi", check=False)
        run_command("sudo pacman -S --noconfirm iperf3", "Instalando iperf3 (opcional)", check=False)
        
    else:
        print("⚠️  Distribución Linux no reconocida")
        print("   Instala manualmente: wireless-tools, iw, network-manager, iperf3")

def install_macos_dependencies():
    """Instala dependencias específicas de macOS"""
    print("\n🍎 Configuración para macOS...")
    
    # airport y system_profiler ya están incluidos
    print("✅ airport y system_profiler ya están disponibles en macOS")
    
    # Intentar instalar iperf3 con Homebrew
    if run_command("brew --version", "Verificando Homebrew", check=False):
        run_command("brew install iperf3", "Instalando iperf3 (opcional)", check=False)
    else:
        print("⚠️  Homebrew no disponible. Instala desde: https://brew.sh/")
        print("   Luego ejecuta: brew install iperf3")

def check_wifi_tools():
    """Verifica que las herramientas WiFi estén disponibles"""
    print("\n🔍 Verificando herramientas WiFi...")
    
    system_os = platform.system()
    
    if system_os == "Windows":
        tools = [("netsh", "netsh wlan show interfaces")]
        
    elif system_os == "Linux":
        tools = [
            ("iwconfig", "iwconfig --version"),
            ("iw", "iw --version"),
            ("nmcli", "nmcli --version")
        ]
        
    elif system_os == "Darwin":  # macOS
        tools = [
            ("airport", "ls /System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"),
            ("system_profiler", "system_profiler -help")
        ]
    else:
        print(f"⚠️  Sistema {system_os} no soportado")
        return False
    
    available_tools = 0
    for tool_name, command in tools:
        if run_command(command, f"Verificando {tool_name}", check=False):
            available_tools += 1
    
    if available_tools > 0:
        print(f"✅ {available_tools}/{len(tools)} herramientas WiFi disponibles")
        return True
    else:
        print("❌ No se encontraron herramientas WiFi")
        return False

def create_desktop_shortcut():
    """Crea un acceso directo en el escritorio"""
    print("\n🖥️  Creando acceso directo...")
    
    system_os = platform.system()
    script_path = os.path.abspath("heapMap-jc.py")
    
    if system_os == "Windows":
        # Crear archivo .bat para Windows
        shortcut_content = f"""@echo off
cd /d "{os.path.dirname(script_path)}"
python "{script_path}"
pause"""
        
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "WiFi_Heatmap.bat")
        try:
            with open(desktop_path, "w") as f:
                f.write(shortcut_content)
            print(f"✅ Acceso directo creado: {desktop_path}")
        except Exception as e:
            print(f"⚠️  No se pudo crear acceso directo: {e}")
            
    elif system_os == "Linux":
        # Crear archivo .desktop para Linux
        shortcut_content = f"""[Desktop Entry]
Name=WiFi Heatmap Generator
Comment=Generador de mapas de calor WiFi
Exec=python3 "{script_path}"
Icon=network-wireless
Terminal=false
Type=Application
Categories=Network;Utility;"""
        
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "wifi-heatmap.desktop")
        try:
            with open(desktop_path, "w") as f:
                f.write(shortcut_content)
            os.chmod(desktop_path, 0o755)
            print(f"✅ Acceso directo creado: {desktop_path}")
        except Exception as e:
            print(f"⚠️  No se pudo crear acceso directo: {e}")
            
    elif system_os == "Darwin":  # macOS
        print("ℹ️  En macOS, agrega el script al Dock arrastrando el archivo")

def main():
    print("🌐 WiFi Heatmap Generator Pro v7 - Instalador")
    print("=" * 50)
    
    # Verificar Python
    if not check_python_version():
        print("\n❌ Error crítico: Versión de Python no compatible")
        sys.exit(1)
    
    # Instalar dependencias Python
    install_python_dependencies()
    
    # Instalar dependencias específicas del sistema
    system_os = platform.system()
    print(f"\n🖥️  Sistema operativo: {system_os}")
    
    if system_os == "Windows":
        install_windows_dependencies()
    elif system_os == "Linux":
        install_linux_dependencies()
    elif system_os == "Darwin":  # macOS
        install_macos_dependencies()
    else:
        print(f"⚠️  Sistema {system_os} no reconocido")
    
    # Verificar herramientas WiFi
    wifi_ok = check_wifi_tools()
    
    # Crear acceso directo
    if os.path.exists("heapMap-jc.py"):
        create_desktop_shortcut()
    else:
        print("⚠️  No se encontró heapMap-jc.py en el directorio actual")
    
    # Resumen final
    print("\n" + "=" * 50)
    print("📋 RESUMEN DE INSTALACIÓN")
    print("=" * 50)
    
    print("✅ Dependencias Python: Instaladas")
    
    if wifi_ok:
        print("✅ Herramientas WiFi: Disponibles")
    else:
        print("⚠️  Herramientas WiFi: Algunas no disponibles")
    
    if run_command("iperf3 --version", "Verificando iperf3", check=False):
        print("✅ iperf3: Disponible (medición de velocidad habilitada)")
    else:
        print("⚠️  iperf3: No disponible (medición de velocidad deshabilitada)")
    
    print("\n🎉 ¡Instalación completada!")
    print("\nPara ejecutar la aplicación:")
    print("   python heapMap-jc.py")
    print("\nPara más información, consulta el README.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Instalación cancelada por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado durante la instalación: {e}")
        sys.exit(1)
