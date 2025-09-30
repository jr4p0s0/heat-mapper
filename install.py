#!/usr/bin/env python3
"""
Script de Instalación para WiFi Heatmap Generator
Detecta el sistema operativo e instala las dependencias necesarias.
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
                                  capture_output=True, text=True, encoding='utf-8', errors='ignore')
        else:
            result = subprocess.run(command, check=check, 
                                  capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
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
        "pillow",
        "iperf3",
        "seaborn"  # <-- Dependencia añadida
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
    
    print("✅ netsh y wmic ya están disponibles en Windows")
    
    if run_command("winget --version", "Verificando winget", check=False):
        print("✅ Winget encontrado. Intentando instalar iperf3...")
        run_command(
            "winget install -e --id iperf.iperf3 --silent --accept-package-agreements --accept-source-agreements",
            "Instalando iperf3 con winget",
            check=False
        )
    else:
        print("⚠️  winget no disponible. Para medir velocidad, instala iperf3 manualmente desde: https://iperf.fr/iperf-download.php")

def install_linux_dependencies():
    """Instala dependencias específicas de Linux"""
    print("\n🐧 Configuración para Linux...")
    
    try:
        with open("/etc/os-release", "r") as f:
            os_info = f.read().lower()
    except FileNotFoundError:
        os_info = ""
    
    if "ubuntu" in os_info or "debian" in os_info:
        print("📋 Sistema Debian/Ubuntu detectado")
        run_command("sudo apt-get update", "Actualizando repositorios", check=False)
        run_command("sudo apt-get install -y wireless-tools iw network-manager iperf3", "Instalando herramientas WiFi e iperf3", check=False)
    elif "fedora" in os_info or "rhel" in os_info or "centos" in os_info:
        print("📋 Sistema RedHat/Fedora detectado")
        if not run_command("sudo dnf install -y wireless-tools iw NetworkManager iperf3", "Instalando herramientas con dnf", check=False):
            run_command("sudo yum install -y wireless-tools iw NetworkManager iperf3", "Instalando herramientas con yum", check=False)
    elif "arch" in os_info:
        print("📋 Sistema Arch Linux detectado")
        run_command("sudo pacman -Syu --noconfirm wireless_tools iw networkmanager iperf3", "Instalando herramientas con pacman", check=False)
    else:
        print("⚠️  Distribución Linux no reconocida. Instala manualmente: wireless-tools, iw, network-manager, iperf3")

def install_macos_dependencies():
    """Instala dependencias específicas de macOS"""
    print("\n🍎 Configuración para macOS...")
    
    print("✅ airport y system_profiler ya están disponibles en macOS")
    
    if run_command("brew --version", "Verificando Homebrew", check=False):
        run_command("brew install iperf3", "Instalando iperf3 con Homebrew", check=False)
    else:
        print("⚠️  Homebrew no disponible. Para medir velocidad, instálalo desde https://brew.sh/ y luego ejecuta: brew install iperf3")

def create_desktop_shortcut():
    """Crea un acceso directo en el escritorio"""
    script_name = "HEAT-MAPPER.PY"  # <-- Nombre corregido
    if not os.path.exists(script_name):
        print(f"⚠️  No se encontró {script_name} para crear el acceso directo.")
        return

    print("\n🖥️  Creando acceso directo...")
    
    system_os = platform.system()
    script_path = os.path.abspath(script_name)
    
    if system_os == "Windows":
        shortcut_content = f'@echo off\ncd /d "{os.path.dirname(script_path)}"\n"{sys.executable}" "{script_path}"'
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "WiFi_Heatmap.bat")
        try:
            with open(desktop_path, "w") as f: f.write(shortcut_content)
            print(f"✅ Acceso directo creado: {desktop_path}")
        except Exception as e:
            print(f"⚠️  No se pudo crear el acceso directo: {e}")
            
    elif system_os == "Linux":
        shortcut_content = f"""[Desktop Entry]
Name=WiFi Heatmap Generator
Comment=Generador de mapas de calor WiFi
Exec={sys.executable} "{script_path}"
Icon=network-wireless
Terminal=false
Type=Application
Categories=Network;"""
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "wifi-heatmap.desktop")
        try:
            with open(desktop_path, "w") as f: f.write(shortcut_content)
            os.chmod(desktop_path, 0o755)
            print(f"✅ Acceso directo creado: {desktop_path}")
        except Exception as e:
            print(f"⚠️  No se pudo crear el acceso directo: {e}")
            
    elif system_os == "Darwin":
        print("ℹ️  En macOS, para crear un acceso directo, arrastra el archivo .py al Dock o al Escritorio.")

def main():
    print("🌐 WiFi Heatmap Generator - Instalador")
    print("=" * 50)
    
    if not check_python_version():
        sys.exit(1)
    
    install_python_dependencies()
    
    system_os = platform.system()
    print(f"\n🖥️  Sistema operativo detectado: {system_os}")
    
    if system_os == "Windows":
        install_windows_dependencies()
    elif system_os == "Linux":
        install_linux_dependencies()
    elif system_os == "Darwin":
        install_macos_dependencies()
    else:
        print(f"⚠️  Sistema {system_os} no completamente soportado. La instalación de herramientas del sistema puede requerir intervención manual.")
    
    create_desktop_shortcut()
    
    print("\n" + "=" * 50)
    print("📋 RESUMEN DE INSTALACIÓN")
    print("=" * 50)
    
    if run_command(f'"{sys.executable}" -m pip show numpy matplotlib scipy pillow iperf3 seaborn', "Verificando dependencias de Python", check=False):
        print("✅ Dependencias de Python instaladas.")
    else:
        print("⚠️  Algunas dependencias de Python pueden haber fallado. Revisa los mensajes de error.")
    
    if run_command("iperf3 --version", "Verificando iperf3", check=False):
        print("✅ iperf3 disponible (medición de velocidad habilitada).")
    else:
        print("⚠️  iperf3 no disponible (medición de velocidad deshabilitada).")
    
    print("\n🎉 ¡Instalación completada!")
    print("\nPara ejecutar la aplicación, usa el acceso directo o ejecuta:")
    print(f'   python {os.path.basename("HEAT-MAPPER.PY")}') # <-- Nombre corregido

if __name__ == "__main__":
    main()