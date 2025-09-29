# 🌐 WiFi Heatmap Generator Pro v7

Generador de mapas de calor WiFi multiplataforma con interfaz moderna. Compatible con **Windows**, **Linux** y **macOS**.

![Python](https://img.shields.io/badge/python-v3.7+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🚀 Características Principales

### 📡 **Detección WiFi Multiplataforma**
- **Windows**: `netsh wlan` + `wmic` 
- **Linux**: `iwconfig` + `iw` + `nmcli` + `/proc/net/wireless`
- **macOS**: `airport` + `system_profiler`

### 📊 **Mediciones Avanzadas**
- ✅ RSSI (señal WiFi) en ambas bandas (2.4GHz y 5GHz)
- ✅ Velocidad de internet con **iperf3** (descarga/subida)
- ✅ Muestreo automático (10 mediciones con intervalo de 2s)
- ✅ Modo manual para valores personalizados

### 🎨 **Interfaz Moderna**
- 🌙 Tema oscuro profesional
- 📱 Controles organizados en secciones
- 🎯 Feedback visual en tiempo real
- 💾 Gestión completa de archivos (JSON)

### 🗺️ **Mapas de Calor**
- 📈 Interpolación cúbica para suavizado
- 🎨 Escala de colores profesional
- 🏗️ Superposición en planos de planta
- 💾 Exportación en PNG, PDF, SVG

## 📋 Requisitos

### Dependencias Python
```bash
pip install matplotlib numpy scipy pillow
```

### Herramientas del Sistema

#### Windows
```powershell
# Incluidas en Windows (netsh, wmic)
# Para iperf3 (opcional):
winget install iperf3
```

#### Linux (Ubuntu/Debian)
```bash
# Herramientas WiFi básicas
sudo apt update
sudo apt install wireless-tools iw network-manager

# Para iperf3 (opcional)
sudo apt install iperf3
```

#### Linux (RHEL/Fedora/CentOS)
```bash
# Herramientas WiFi básicas  
sudo yum install wireless-tools iw NetworkManager
# o para Fedora más reciente:
sudo dnf install wireless-tools iw NetworkManager

# Para iperf3 (opcional)
sudo yum install iperf3  # o dnf install iperf3
```

#### macOS
```bash
# Herramientas incluidas por defecto
# Para iperf3 (opcional):
brew install iperf3
```

## 🚀 Instalación y Uso

### 1️⃣ Clonar y Preparar
```bash
# Descargar el archivo
# Instalar dependencias
pip install matplotlib numpy scipy pillow

# Ejecutar
python HEAT-MAPPER.py
```

### 2️⃣ Uso Básico

#### **Paso 1: Cargar Plano**
- Clic en "🏗️ Cargar Plano de Planta"
- Seleccionar imagen (PNG, JPG, etc.)

#### **Paso 2: Colocar Puntos**
- Hacer clic en el plano donde medir
- Se creará un punto numerado

#### **Paso 3: Realizar Mediciones**
- **Modo Automático**: Detecta WiFi automáticamente
- **Modo Manual**: Introducir RSSI personalizado
- **📍 Medición Simple**: 1 medición
- **🔄 Medición x10**: 10 mediciones con pausa de 2s

#### **Paso 4: Generar Mapa**
- Seleccionar banda (2.4GHz o 5GHz)
- Clic en "🎨 Generar Mapa de Calor"
- Elegir ubicación para guardar

## 🔧 Configuración de iperf3 (Opcional)

Para medir velocidades de internet necesitas un servidor iperf3:

### Servidor iperf3
```bash
# En el router o PC servidor
iperf3 -s

# En puerto específico
iperf3 -s -p 5201
```

### Cliente (Aplicación)
- Marcar "⚡ Medir Velocidad (iperf3)"
- Introducir IP del servidor (ej: 192.168.1.1)

## 📊 Interpretación de Resultados

### Colores de Puntos
- 🟣 **Púrpura**: Mediciones en 2.4GHz y 5GHz
- 🔵 **Azul**: Solo 2.4GHz  
- 🔴 **Rojo**: Solo 5GHz
- ⚪ **Gris**: Sin mediciones

### Escala RSSI (dBm)
- **-30 a -50**: 🟢 Excelente
- **-50 a -60**: 🟡 Buena  
- **-60 a -70**: 🟠 Regular
- **-70 a -80**: 🔴 Mala
- **< -80**: ⚫ Muy mala

## 🗂️ Formato de Archivos

### Datos (.json)
```json
{
  "ssid": "MiRed_WiFi",
  "timestamp": "2024-01-15T10:30:00",
  "system_os": "Windows",
  "points": [
    {
      "id": 1,
      "x": 150, "y": 200,
      "rssi_2.4": [-45, -47, -46],
      "rssi_5": [-52, -50, -51],
      "dl_2.4": [85.5, 87.2], 
      "ul_2.4": [23.1, 24.0],
      "dl_5": [156.8, 159.1],
      "ul_5": [45.2, 46.8]
    }
  ]
}
```

## 🐛 Solución de Problemas

### Windows
```powershell
# Verificar WiFi activo
netsh wlan show interfaces

# Ejecutar como administrador si hay problemas
```

### Linux
```bash
# Verificar herramientas
which iwconfig iw nmcli

# Verificar permisos
sudo usermod -a -G netdev $USER  # Logout y login

# Verificar interfaces WiFi
ip link show
```

### macOS
```bash
# Verificar airport
ls /System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/

# Permisos de ubicación
# System Preferences > Security & Privacy > Privacy > Location Services
```

## 🤝 Contribuir

1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)  
5. Abrir Pull Request

## 📝 Historial de Versiones

- **v7.0**: Compatibilidad multiplataforma + interfaz moderna
- **v6.0**: Integración iperf3 + muestreo automático  
- **v5.0**: Mapas de calor mejorados
- **v4.0**: Interfaz gráfica básica

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

---

**🌟 ¿Te gusta el proyecto? ¡Deja una estrella!**
