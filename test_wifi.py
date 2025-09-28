#!/usr/bin/env python3
"""
Script de Prueba para WiFi Heatmap Generator Pro v7
Prueba las funcionalidades de detección WiFi en cada sistema operativo
"""

import subprocess
import platform
import sys
import json
from datetime import datetime

def test_wifi_detection():
    """Prueba la detección WiFi usando las mismas funciones del programa principal"""
    
    def get_wifi_rssi_windows():
        """Prueba métodos de Windows"""
        methods_tested = []
        
        # Método 1: netsh wlan
        try:
            result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], 
                                  capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                output = result.stdout
                ssid_match = None
                signal_match = None
                
                for line in output.split('\n'):
                    if 'SSID' in line and ':' in line:
                        ssid_match = line.split(':', 1)[1].strip()
                    elif 'Signal' in line and '%' in line:
                        signal_match = line.split(':')[1].strip().replace('%', '')
                
                if ssid_match and signal_match:
                    try:
                        signal_percent = int(signal_match)
                        rssi = int((signal_percent / 2) - 100)
                        methods_tested.append({
                            'method': 'netsh wlan',
                            'success': True,
                            'ssid': ssid_match,
                            'rssi': rssi,
                            'band': '2.4'
                        })
                    except ValueError:
                        methods_tested.append({
                            'method': 'netsh wlan',
                            'success': False,
                            'error': 'No se pudo parsear señal'
                        })
                else:
                    methods_tested.append({
                        'method': 'netsh wlan',
                        'success': False,
                        'error': 'No se encontraron SSID o señal'
                    })
            else:
                methods_tested.append({
                    'method': 'netsh wlan',
                    'success': False,
                    'error': f'Comando falló: {result.stderr}'
                })
        except Exception as e:
            methods_tested.append({
                'method': 'netsh wlan',
                'success': False,
                'error': str(e)
            })
        
        # Método 2: wmic
        try:
            result = subprocess.run(['wmic', 'path', 'win32_networkadapter', 'where', 
                                   'NetConnectionStatus=2', 'get', 'Name,NetConnectionID'], 
                                  capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                methods_tested.append({
                    'method': 'wmic',
                    'success': True,
                    'ssid': 'Red WiFi Activa (detectada)',
                    'rssi': -50,
                    'band': '2.4',
                    'note': 'Método de respaldo con valores por defecto'
                })
            else:
                methods_tested.append({
                    'method': 'wmic',
                    'success': False,
                    'error': f'wmic falló: {result.stderr}'
                })
        except Exception as e:
            methods_tested.append({
                'method': 'wmic',
                'success': False,
                'error': str(e)
            })
        
        return methods_tested

    def get_wifi_rssi_linux():
        """Prueba métodos de Linux"""
        methods_tested = []
        
        # Método 1: iwconfig
        try:
            result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                output = result.stdout
                if 'IEEE 802.11' in output:
                    # Buscar interfaz activa
                    lines = output.split('\n')
                    current_interface = None
                    
                    for line in lines:
                        if 'IEEE 802.11' in line:
                            current_interface = line.split()[0]
                        elif current_interface and 'ESSID:' in line and 'off/any' not in line:
                            # Obtener info específica de esta interfaz
                            try:
                                iface_result = subprocess.run(['iwconfig', current_interface], 
                                                            capture_output=True, text=True, timeout=5)
                                if iface_result.returncode == 0:
                                    iface_output = iface_result.stdout
                                    
                                    ssid = None
                                    rssi = None
                                    
                                    for iface_line in iface_output.split('\n'):
                                        if 'ESSID:' in iface_line:
                                            ssid = iface_line.split('ESSID:')[1].strip().strip('"')
                                        elif 'Signal level=' in iface_line:
                                            signal_part = iface_line.split('Signal level=')[1].split()[0]
                                            try:
                                                rssi = int(signal_part)
                                            except ValueError:
                                                pass
                                    
                                    if ssid and rssi:
                                        methods_tested.append({
                                            'method': 'iwconfig',
                                            'success': True,
                                            'ssid': ssid,
                                            'rssi': rssi,
                                            'band': '2.4',
                                            'interface': current_interface
                                        })
                                        break
                            except:
                                pass
                
                if not any(m.get('success') for m in methods_tested if m.get('method') == 'iwconfig'):
                    methods_tested.append({
                        'method': 'iwconfig',
                        'success': False,
                        'error': 'No se encontraron redes WiFi activas'
                    })
            else:
                methods_tested.append({
                    'method': 'iwconfig',
                    'success': False,
                    'error': 'iwconfig no disponible o falló'
                })
        except Exception as e:
            methods_tested.append({
                'method': 'iwconfig',
                'success': False,
                'error': str(e)
            })
        
        # Método 2: iw dev
        try:
            dev_result = subprocess.run(['iw', 'dev'], capture_output=True, text=True, timeout=5)
            if dev_result.returncode == 0:
                interfaces = []
                for line in dev_result.stdout.split('\n'):
                    if 'Interface' in line:
                        interfaces.append(line.split('Interface')[1].strip())
                
                for interface in interfaces:
                    try:
                        link_result = subprocess.run(['iw', interface, 'link'], 
                                                   capture_output=True, text=True, timeout=5)
                        if link_result.returncode == 0 and ('Connected to' in link_result.stdout or 'SSID' in link_result.stdout):
                            ssid = None
                            rssi = None
                            
                            for line in link_result.stdout.split('\n'):
                                if 'SSID:' in line:
                                    ssid = line.split('SSID:')[1].strip()
                                elif 'signal:' in line:
                                    try:
                                        rssi = int(line.split('signal:')[1].split()[0])
                                    except:
                                        pass
                            
                            if ssid and rssi:
                                methods_tested.append({
                                    'method': 'iw',
                                    'success': True,
                                    'ssid': ssid,
                                    'rssi': rssi,
                                    'band': '2.4',
                                    'interface': interface
                                })
                                break
                    except:
                        continue
                
                if not any(m.get('success') for m in methods_tested if m.get('method') == 'iw'):
                    methods_tested.append({
                        'method': 'iw',
                        'success': False,
                        'error': 'No se encontraron conexiones activas'
                    })
            else:
                methods_tested.append({
                    'method': 'iw',
                    'success': False,
                    'error': 'iw no disponible'
                })
        except Exception as e:
            methods_tested.append({
                'method': 'iw',
                'success': False,
                'error': str(e)
            })
        
        # Método 3: nmcli
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL', 'dev', 'wifi'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split(':')
                    if len(parts) >= 3 and parts[0] == 'yes':  # Conexión activa
                        ssid = parts[1]
                        signal = parts[2]
                        
                        if ssid and signal.isdigit():
                            rssi = int((int(signal) / 2) - 100)
                            methods_tested.append({
                                'method': 'nmcli',
                                'success': True,
                                'ssid': ssid,
                                'rssi': rssi,
                                'band': '2.4'
                            })
                            break
                
                if not any(m.get('success') for m in methods_tested if m.get('method') == 'nmcli'):
                    methods_tested.append({
                        'method': 'nmcli',
                        'success': False,
                        'error': 'No se encontraron conexiones activas'
                    })
            else:
                methods_tested.append({
                    'method': 'nmcli',
                    'success': False,
                    'error': 'nmcli no disponible'
                })
        except Exception as e:
            methods_tested.append({
                'method': 'nmcli',
                'success': False,
                'error': str(e)
            })
        
        return methods_tested

    def get_wifi_rssi_macos():
        """Prueba métodos de macOS"""
        methods_tested = []
        
        # Método 1: airport
        try:
            airport_path = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            result = subprocess.run([airport_path, "-I"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                ssid = None
                rssi = None
                channel = None
                
                for line in output.split('\n'):
                    line = line.strip()
                    if line.startswith('SSID:'):
                        ssid = line.split(':', 1)[1].strip()
                    elif 'RSSI:' in line or 'agrCtlRSSI:' in line:
                        try:
                            rssi = int(line.split(':')[1].strip())
                        except:
                            pass
                    elif line.startswith('channel:'):
                        try:
                            channel = int(line.split(':')[1].strip())
                        except:
                            pass
                
                if ssid and rssi:
                    band = '5' if channel and channel > 14 else '2.4'
                    methods_tested.append({
                        'method': 'airport',
                        'success': True,
                        'ssid': ssid,
                        'rssi': rssi,
                        'band': band,
                        'channel': channel
                    })
                else:
                    methods_tested.append({
                        'method': 'airport',
                        'success': False,
                        'error': 'No se pudo extraer información'
                    })
            else:
                methods_tested.append({
                    'method': 'airport',
                    'success': False,
                    'error': f'airport falló: {result.stderr}'
                })
        except Exception as e:
            methods_tested.append({
                'method': 'airport',
                'success': False,
                'error': str(e)
            })
        
        # Método 2: system_profiler
        try:
            result = subprocess.run(['system_profiler', 'SPAirPortDataType'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and "Current Network Information" in result.stdout:
                network_section = result.stdout.split("Current Network Information:")[1]
                
                ssid = None
                rssi = None
                channel = None
                
                lines = network_section.split('\n')
                for i, line in enumerate(lines):
                    line = line.strip()
                    if ':' in line and not line.startswith(' ') and i < 10:  # Probable SSID
                        potential_ssid = line.split(':')[0].strip()
                        if potential_ssid and not any(word in potential_ssid.lower() 
                                                    for word in ['signal', 'channel', 'security']):
                            ssid = potential_ssid
                    elif 'Signal / Noise' in line or 'RSSI:' in line:
                        try:
                            rssi_part = line.split(':')[1].strip().split()[0]
                            rssi = int(rssi_part)
                        except:
                            pass
                    elif 'Channel:' in line:
                        try:
                            channel = int(line.split(':')[1].strip())
                        except:
                            pass
                
                if ssid and rssi:
                    band = '5' if channel and channel > 14 else '2.4'
                    methods_tested.append({
                        'method': 'system_profiler',
                        'success': True,
                        'ssid': ssid,
                        'rssi': rssi,
                        'band': band,
                        'channel': channel
                    })
                else:
                    methods_tested.append({
                        'method': 'system_profiler',
                        'success': False,
                        'error': 'No se pudo extraer información de la red'
                    })
            else:
                methods_tested.append({
                    'method': 'system_profiler',
                    'success': False,
                    'error': 'No hay información de red actual'
                })
        except Exception as e:
            methods_tested.append({
                'method': 'system_profiler',
                'success': False,
                'error': str(e)
            })
        
        return methods_tested

    # Ejecutar pruebas según el sistema operativo
    system_os = platform.system()
    
    print(f"🔍 Probando detección WiFi en {system_os}...")
    print("=" * 50)
    
    if system_os == "Windows":
        results = get_wifi_rssi_windows()
    elif system_os == "Linux":
        results = get_wifi_rssi_linux()
    elif system_os == "Darwin":  # macOS
        results = get_wifi_rssi_macos()
    else:
        print(f"❌ Sistema operativo {system_os} no soportado")
        return False
    
    # Mostrar resultados
    successful_methods = 0
    
    for result in results:
        method = result.get('method', 'Unknown')
        success = result.get('success', False)
        
        if success:
            successful_methods += 1
            print(f"✅ {method}: ÉXITO")
            print(f"   SSID: {result.get('ssid', 'N/A')}")
            print(f"   RSSI: {result.get('rssi', 'N/A')} dBm")
            print(f"   Banda: {result.get('band', 'N/A')} GHz")
            if result.get('interface'):
                print(f"   Interfaz: {result.get('interface')}")
            if result.get('channel'):
                print(f"   Canal: {result.get('channel')}")
            if result.get('note'):
                print(f"   Nota: {result.get('note')}")
        else:
            print(f"❌ {method}: ERROR")
            print(f"   Error: {result.get('error', 'Error desconocido')}")
        print()
    
    print("=" * 50)
    print(f"📊 Resumen: {successful_methods}/{len(results)} métodos funcionando")
    
    return successful_methods > 0

def test_iperf3():
    """Prueba la disponibilidad de iperf3"""
    print("\n⚡ Probando iperf3...")
    print("=" * 30)
    
    try:
        result = subprocess.run(['iperf3', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_info = result.stdout.strip()
            print(f"✅ iperf3 disponible: {version_info}")
            
            # Probar conexión a servidor común (si existe)
            test_servers = ['iperf.scottlinux.com', 'iperf.biznetnetworks.com']
            
            for server in test_servers:
                print(f"\n🔄 Probando conexión a {server}...")
                try:
                    test_result = subprocess.run(['iperf3', '-c', server, '-t', '1'], 
                                               capture_output=True, text=True, timeout=10)
                    if test_result.returncode == 0:
                        print(f"✅ Conexión exitosa a {server}")
                        return True
                    else:
                        print(f"❌ No se pudo conectar a {server}")
                except:
                    print(f"❌ Timeout o error conectando a {server}")
            
            print("\n⚠️  iperf3 está instalado pero no se pudo probar con servidores públicos")
            print("   Para usar la funcionalidad de velocidad:")
            print("   1. Configura un servidor iperf3 local: iperf3 -s")
            print("   2. Usa la IP del servidor en la aplicación")
            
            return True
        else:
            print("❌ iperf3 instalado pero no funciona correctamente")
            return False
            
    except FileNotFoundError:
        print("❌ iperf3 no está instalado")
        
        system_os = platform.system()
        if system_os == "Windows":
            print("   Instala con: winget install iperf3")
        elif system_os == "Linux":
            print("   Instala con: sudo apt install iperf3  (Ubuntu/Debian)")
            print("   Instala con: sudo yum install iperf3  (RHEL/CentOS)")
        elif system_os == "Darwin":
            print("   Instala con: brew install iperf3")
        
        return False
        
    except Exception as e:
        print(f"❌ Error probando iperf3: {e}")
        return False

def test_python_dependencies():
    """Prueba las dependencias de Python"""
    print("\n🐍 Probando dependencias de Python...")
    print("=" * 40)
    
    dependencies = {
        'matplotlib': 'matplotlib.pyplot',
        'numpy': 'numpy',
        'scipy': 'scipy.interpolate', 
        'pillow': 'PIL.Image'
    }
    
    successful_imports = 0
    
    for dep_name, import_name in dependencies.items():
        try:
            __import__(import_name)
            print(f"✅ {dep_name}: OK")
            successful_imports += 1
        except ImportError:
            print(f"❌ {dep_name}: NO INSTALADO")
            print(f"   Instala con: pip install {dep_name}")
        except Exception as e:
            print(f"⚠️  {dep_name}: ERROR - {e}")
    
    print(f"\n📊 {successful_imports}/{len(dependencies)} dependencias disponibles")
    return successful_imports == len(dependencies)

def generate_report():
    """Genera un reporte completo de la prueba"""
    print("\n📋 Generando reporte...")
    
    system_info = {
        'timestamp': datetime.now().isoformat(),
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version()
    }
    
    print("✅ Reporte básico generado")
    
    # Intentar guardar reporte detallado
    try:
        report_file = f"wifi_test_report_{platform.system().lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(system_info, f, indent=2)
            
        print(f"✅ Reporte detallado guardado: {report_file}")
        
    except Exception as e:
        print(f"⚠️  No se pudo guardar reporte detallado: {e}")

def main():
    print("🧪 WiFi Heatmap Generator Pro v7 - Prueba de Funcionalidades")
    print("=" * 65)
    print(f"Sistema: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print("=" * 65)
    
    # Contador de pruebas exitosas
    successful_tests = 0
    total_tests = 3
    
    # Prueba 1: Dependencias Python
    if test_python_dependencies():
        successful_tests += 1
    
    # Prueba 2: Detección WiFi
    if test_wifi_detection():
        successful_tests += 1
    
    # Prueba 3: iperf3
    if test_iperf3():
        successful_tests += 1
    
    # Generar reporte
    generate_report()
    
    # Resumen final
    print("\n" + "=" * 65)
    print("🏁 RESUMEN FINAL")
    print("=" * 65)
    
    if successful_tests == total_tests:
        print("🎉 ¡TODAS LAS PRUEBAS EXITOSAS!")
        print("   La aplicación WiFi Heatmap Generator debería funcionar perfectamente.")
    elif successful_tests >= 2:
        print("✅ MAYORÍA DE PRUEBAS EXITOSAS")
        print("   La aplicación debería funcionar con funcionalidad limitada.")
        if successful_tests == 2:
            print("   Considera instalar las dependencias faltantes para funcionalidad completa.")
    else:
        print("⚠️  POCAS PRUEBAS EXITOSAS")
        print("   Revisa los errores anteriores antes de usar la aplicación.")
    
    print(f"\n📊 Pruebas exitosas: {successful_tests}/{total_tests}")
    print("\nPara más información, consulta el README.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Prueba cancelada por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado durante las pruebas: {e}")
        sys.exit(1)