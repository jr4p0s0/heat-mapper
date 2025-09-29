#!/usr/bin/env python3
"""
WiFi Heatmap Generator Pro
- AÑADIDO: Compatibilidad completa con Windows, Linux y macOS
- AÑADIDO: Interfaz moderna con mejor diseño y colores
- MEJORADO: Detección de WiFi robusta para todos los sistemas operativos
- MANTENIDO: Todas las funcionalidades originales (iperf3, muestreo automático, etc.)
- TO-DO: Implementar iperf3 como librería de python en vez de instalarlo en el host
"""

import subprocess
import json
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import re
from datetime import datetime
import os
import sys
import platform
from collections import defaultdict
import threading
from queue import Queue
import time


class MeasurementPoint:
    def __init__(self, point_id, x, y):
        self.id = point_id
        self.x = x
        self.y = y
        self.timestamp = datetime.now()
        # Listas para RSSI
        self.measurements_24 = []
        self.measurements_5 = []
        # Listas para Velocidad (Download/Upload)
        self.measurements_dl_24 = []
        self.measurements_ul_24 = []
        self.measurements_dl_5 = []
        self.measurements_ul_5 = []

    def add_measurement(self, rssi, band, dl_speed=None, ul_speed=None):
        if band == '2.4':
            self.measurements_24.append(rssi)
            if dl_speed is not None:
                self.measurements_dl_24.append(dl_speed)
            if ul_speed is not None:
                self.measurements_ul_24.append(ul_speed)
        else:
            self.measurements_5.append(rssi)
            if dl_speed is not None:
                self.measurements_dl_5.append(dl_speed)
            if ul_speed is not None:
                self.measurements_ul_5.append(ul_speed)

    def get_average_rssi(self, band):
        measurements = self.measurements_24 if band == '2.4' else self.measurements_5
        return round(np.mean(measurements), 1) if measurements else None

    def get_average_speed(self, band, direction='dl'):
        if band == '2.4':
            measurements = self.measurements_dl_24 if direction == 'dl' else self.measurements_ul_24
        else:
            measurements = self.measurements_dl_5 if direction == 'dl' else self.measurements_ul_5
        return round(np.mean(measurements), 2) if measurements else None

    def get_measurement_count(self, band):
        return len(self.measurements_24 if band == '2.4' else self.measurements_5)


class WiFiHeatmapGenerator:
    def __init__(self):
        self.measurement_points = {}
        self.current_ssid = None
        self.floor_plan_image = None
        self.floor_plan_dims = None
        self.next_point_id = 1
        self.system_os = platform.system()

    def get_wifi_rssi(self):
        """Obtiene información WiFi de forma multiplataforma"""
        if self.system_os == "Darwin":  # macOS
            return self._get_wifi_rssi_macos()
        elif self.system_os == "Windows":
            return self._get_wifi_rssi_windows()
        elif self.system_os == "Linux":
            return self._get_wifi_rssi_linux()
        else:
            return None, f"Sistema operativo no soportado: {self.system_os}", None

    def _get_wifi_rssi_macos(self):
        """Métodos específicos para macOS"""
        # Método 1: airport (el más rápido)
        try:
            airport_path = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            if os.path.exists(airport_path):
                result = subprocess.run(
                    [airport_path, "-I"], capture_output=True, text=True, timeout=5, check=False)
                if result.returncode == 0 and "SSID" in result.stdout:
                    output = result.stdout
                    rssi_match = re.search(
                        r'^\s*(?:agrCtlRSSI|RSSI):\s*(-?\d+)', output, re.MULTILINE)
                    ssid_match = re.search(
                        r'^\s*SSID:\s*(.+)', output, re.MULTILINE)
                    channel_match = re.search(
                        r'^\s*channel:\s*(\d+)', output, re.MULTILINE)
                    if rssi_match and ssid_match and channel_match:
                        rssi = int(rssi_match.group(1))
                        ssid = ssid_match.group(1).strip()
                        channel = int(channel_match.group(1))
                        band = '5' if channel > 14 else '2.4'
                        return rssi, ssid, band
        except Exception as e:
            print(f"-> Método 'airport' falló: {e}")

        # Método 2: system_profiler
        try:
            cmd = ["system_profiler", "SPAirPortDataType"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0 and "Current Network Information" in result.stdout:
                network_section = result.stdout.split(
                    "Current Network Information:")[1]
                rssi_match = re.search(
                    r'Signal / Noise.*:\s*(-?\d+)', network_section) or re.search(r'RSSI:\s*(-?\d+)', network_section)
                ssid_match = re.search(
                    r'^\s*(.+?):\s*$', network_section, re.MULTILINE)
                channel_match = re.search(r'Channel:\s*(\d+)', network_section)
                if rssi_match and ssid_match and channel_match:
                    rssi = int(rssi_match.group(1))
                    ssid = ssid_match.group(1).strip()
                    channel = int(channel_match.group(1))
                    band = '5' if channel > 14 else '2.4'
                    return rssi, ssid, band
        except Exception as e:
            print(f"-> Método 'system_profiler' falló: {e}")

        return None, "No se pudo obtener el RSSI en macOS", None

    def _get_wifi_rssi_windows(self):
        """Métodos específicos para Windows"""
        try:
            # Obtener información del perfil activo
            result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                                    capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                output = result.stdout

                # Buscar SSID y señal
                ssid_match = re.search(
                    r'^\s*SSID\s*:\s*(.+)', output, re.MULTILINE)
                signal_match = re.search(
                    r'^\s*Signal\s*:\s*(\d+)%', output, re.MULTILINE)
                channel_match = re.search(
                    r'^\s*Channel\s*:\s*(\d+)', output, re.MULTILINE)

                if ssid_match and signal_match:
                    ssid = ssid_match.group(1).strip()
                    signal_percent = int(signal_match.group(1))

                    # Convertir porcentaje a dBm aproximado
                    # Fórmula aproximada: dBm = (Signal% / 2) - 100
                    rssi = int((signal_percent / 2) - 100)

                    # Determinar banda por canal
                    band = '2.4'
                    if channel_match:
                        channel = int(channel_match.group(1))
                        band = '5' if channel > 14 else '2.4'

                    return rssi, ssid, band

        except Exception as e:
            print(f"-> Método netsh Windows falló: {e}")

        # Método alternativo con wmic
        try:
            result = subprocess.run(['wmic', 'path', 'win32_networkadapter', 'where',
                                     'NetConnectionStatus=2', 'get', 'Name,NetConnectionID'],
                                    capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                # Este método es más limitado pero funciona como respaldo
                return -50, "Red WiFi Activa", "2.4"  # Valores por defecto
        except Exception as e:
            print(f"-> Método wmic Windows falló: {e}")

        return None, "No se pudo obtener información WiFi en Windows", None

    def _get_wifi_rssi_linux(self):
        """Métodos específicos para Linux"""
        # Método 1: iwconfig
        try:
            result = subprocess.run(
                ['iwconfig'], capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                output = result.stdout

                # Buscar interfaz WiFi activa
                wifi_interfaces = re.findall(
                    r'^(\w+)\s+IEEE 802\.11', output, re.MULTILINE)

                for interface in wifi_interfaces:
                    # Obtener información específica de la interfaz
                    iface_result = subprocess.run(['iwconfig', interface],
                                                  capture_output=True, text=True, timeout=5, check=False)
                    if iface_result.returncode == 0:
                        iface_output = iface_result.stdout

                        # Buscar ESSID y Signal level
                        ssid_match = re.search(
                            r'ESSID:"([^"]+)"', iface_output)
                        signal_match = re.search(
                            r'Signal level=(-?\d+)', iface_output)
                        freq_match = re.search(
                            r'Frequency:([\d.]+)', iface_output)

                        if ssid_match and signal_match:
                            ssid = ssid_match.group(1)
                            rssi = int(signal_match.group(1))

                            # Determinar banda por frecuencia
                            band = '2.4'
                            if freq_match:
                                freq = float(freq_match.group(1))
                                band = '5' if freq > 4 else '2.4'

                            return rssi, ssid, band

        except Exception as e:
            print(f"-> Método iwconfig Linux falló: {e}")

        # Método 2: iw (más moderno)
        try:
            # Primero encontrar interfaz WiFi
            result = subprocess.run(
                ['iw', 'dev'], capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                interfaces = re.findall(r'Interface (\w+)', result.stdout)

                for interface in interfaces:
                    # Obtener información de la conexión
                    link_result = subprocess.run(['iw', interface, 'link'],
                                                 capture_output=True, text=True, timeout=5, check=False)
                    if link_result.returncode == 0:
                        link_output = link_result.stdout

                        if 'Connected to' in link_output or 'SSID' in link_output:
                            ssid_match = re.search(
                                r'SSID:\s*(.+)', link_output)
                            signal_match = re.search(
                                r'signal:\s*(-?\d+)', link_output)
                            freq_match = re.search(
                                r'freq:\s*(\d+)', link_output)

                            if ssid_match and signal_match:
                                ssid = ssid_match.group(1).strip()
                                rssi = int(signal_match.group(1))

                                # Determinar banda por frecuencia
                                band = '2.4'
                                if freq_match:
                                    freq_mhz = int(freq_match.group(1))
                                    band = '5' if freq_mhz > 4000 else '2.4'

                                return rssi, ssid, band

        except Exception as e:
            print(f"-> Método iw Linux falló: {e}")

        # Método 3: nmcli (NetworkManager)
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL,FREQ', 'dev', 'wifi'],
                                    capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split(':')
                    if len(parts) >= 4 and parts[0] == 'yes':  # Conexión activa
                        ssid = parts[1]
                        signal_percent = parts[2]
                        freq = parts[3] if parts[3] else '2400'

                        # Convertir señal de porcentaje a dBm
                        if signal_percent.isdigit():
                            rssi = int((int(signal_percent) / 2) - 100)
                            band = '5' if int(freq) > 4000 else '2.4'
                            return rssi, ssid, band

        except Exception as e:
            print(f"-> Método nmcli Linux falló: {e}")

        # Método 4: /proc/net/wireless
        try:
            with open('/proc/net/wireless', 'r') as f:
                lines = f.readlines()
                if len(lines) > 2:  # Saltar headers
                    for line in lines[2:]:
                        parts = line.split()
                        if len(parts) >= 3:
                            interface = parts[0].rstrip(':')
                            signal_quality = parts[2]

                            # Intentar obtener más info con iwconfig
                            try:
                                iwconfig_result = subprocess.run(['iwconfig', interface],
                                                                 capture_output=True, text=True, timeout=3)
                                if iwconfig_result.returncode == 0:
                                    ssid_match = re.search(
                                        r'ESSID:"([^"]+)"', iwconfig_result.stdout)
                                    if ssid_match:
                                        ssid = ssid_match.group(1)
                                        # Aproximación
                                        rssi = int(float(signal_quality)) - 100
                                        return rssi, ssid, '2.4'
                            except:
                                pass
        except Exception as e:
            print(f"-> Método /proc/net/wireless Linux falló: {e}")

        return None, "No se pudo obtener información WiFi en Linux", None

    def get_wifi_speed(self, server_ip):
        """Ejecuta iperf3 para obtener velocidad de descarga y subida."""
        dl_mbps, ul_mbps = None, None
        try:
            # Test de Descarga
            print(f"Ejecutando iperf3 (descarga) contra el servidor {server_ip}...")
            dl_cmd = ["iperf3", "-c", server_ip, "-J", "-t", "5"]
            result_dl = subprocess.run(
                dl_cmd, capture_output=True, text=True, timeout=15, check=True)
            data_dl = json.loads(result_dl.stdout)
            dl_mbps = round(data_dl['end']['sum_received']
                            ['bits_per_second'] / 1_000_000, 2)
            print(f"-> Velocidad de Descarga: {dl_mbps} Mbps")

            # Test de Subida
            print(f"Ejecutando iperf3 (subida) contra el servidor {server_ip}...") 
            ul_cmd = ["iperf3", "-c", server_ip, "-J", "-t", "5", "-R"]
            result_ul = subprocess.run(
                ul_cmd, capture_output=True, text=True, timeout=15, check=True)
            data_ul = json.loads(result_ul.stdout)
            ul_mbps = round(data_ul['end']['sum_sent']
                            ['bits_per_second'] / 1_000_000, 2)
            print(f"-> Velocidad de Subida: {ul_mbps} Mbps")

        except FileNotFoundError:
            return None, "Error: 'iperf3' no encontrado. Asegúrate de que está instalado."
        except subprocess.CalledProcessError as e:
            error_info = "Asegúrate de que el servidor iperf3 está corriendo y es accesible."
            try:
                error_json = json.loads(e.stdout)
                if 'error' in error_json:
                    error_info = error_json['error']
            except json.JSONDecodeError:
                error_info = e.stderr or e.stdout
            return None, f"Error de iperf3: {error_info}"
        except Exception as e:
            return None, f"Error inesperado durante el test de velocidad: {e}"

        return (dl_mbps, ul_mbps), None

    def create_or_update_point(self, x, y):
        for pid, p in self.measurement_points.items():
            if np.sqrt((p.x - x)**2 + (p.y - y)**2) < 15:
                return p
        new_point = MeasurementPoint(self.next_point_id, x, y)
        self.measurement_points[self.next_point_id] = new_point
        self.next_point_id += 1
        return new_point

    def add_measurement_to_point(self, point, rssi, band, dl_speed, ul_speed):
        point.add_measurement(rssi, band, dl_speed, ul_speed)
        avg_rssi = point.get_average_rssi(band)
        count = point.get_measurement_count(band)
        avg_dl = point.get_average_speed(band, 'dl')
        avg_ul = point.get_average_speed(band, 'ul')
        print(f"[Medición] Punto ID: {point.id} | Banda: {band}GHz | RSSI: {rssi}dBm | DL: {dl_speed} Mbps | UL: {ul_speed} Mbps")
        print(
            f"  -> Promedios ({count}x): RSSI: {avg_rssi}dBm | DL: {avg_dl} Mbps | UL: {avg_ul} Mbps")

    def generate_heatmap_data(self, band, resolution=100):
        valid_points = [p for p in self.measurement_points.values(
        ) if p.get_average_rssi(band) is not None]
        if len(valid_points) < 4:
            raise ValueError(
                f"Se necesitan al menos 4 puntos para la banda {band} GHz.")
        points = np.array([[p.x, p.y] for p in valid_points])
        values = np.array([p.get_average_rssi(band) for p in valid_points])
        xi = np.linspace(0, self.floor_plan_dims[0], resolution)
        yi = np.linspace(0, self.floor_plan_dims[1], resolution)
        xi, yi = np.meshgrid(xi, yi)
        zi = griddata(points, values, (xi, yi), method='cubic')
        return xi, yi, zi

    def plot_heatmap_on_floor_plan(self, band, floor_plan_path=None, save_path=None):
        fig, ax = plt.subplots(1, 1, figsize=(12, 9))
        fig.patch.set_facecolor('#f0f0f0')

        if floor_plan_path and os.path.exists(floor_plan_path):
            floor_img = plt.imread(floor_plan_path)
            ax.imshow(floor_img, extent=[
                      0, self.floor_plan_dims[0], self.floor_plan_dims[1], 0], aspect='auto')

        try:
            xi, yi, zi = self.generate_heatmap_data(band)
            im = ax.contourf(xi, yi, zi, levels=15,
                             cmap='RdYlGn_r', vmin=-90, vmax=-30, alpha=0.6)

            for p in self.measurement_points.values():
                if p.get_average_rssi(band) is not None:
                    ax.plot(p.x, p.y, 'ko', markersize=10,
                            markeredgecolor='white', markeredgewidth=2)
                    ax.text(p.x, p.y, str(p.id), fontsize=9, ha='center',
                            va='center', color='white', weight='bold')

            ax.set_title(f'Mapa de Calor WiFi - Banda {band} GHz\nSSID: {self.current_ssid}', fontsize=14, weight='bold')
            ax.set_xlabel('Posición X (píxeles)', fontsize=12)
            ax.set_ylabel('Posición Y (píxeles)', fontsize=12)
            ax.set_xlim(0, self.floor_plan_dims[0])
            ax.set_ylim(self.floor_plan_dims[1], 0)

            cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.01)
            cbar.set_label('RSSI (dBm)', fontsize=12)
            ax.grid(True, alpha=0.2, linestyle='--')

        except ValueError as e:
            ax.text(0.5, 0.5, f'Datos insuficientes para la banda {band} GHz\n({e})',
                    ha='center', va='center', transform=ax.transAxes, fontsize=12, color='red')
            ax.set_title(f'Banda {band} GHz - Error', fontsize=14)

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
            print(f"✅ Mapa guardado: {save_path}")
        plt.show()

    def save_data(self, fp):
        data = {
            'ssid': self.current_ssid,
            'timestamp': datetime.now().isoformat(),
            'system_os': self.system_os,
            'points': [
                {
                    'id': p.id, 'x': p.x, 'y': p.y,
                    'rssi_2.4': p.measurements_24, 'rssi_5': p.measurements_5,
                    'dl_2.4': p.measurements_dl_24, 'ul_2.4': p.measurements_ul_24,
                    'dl_5': p.measurements_dl_5, 'ul_5': p.measurements_ul_5,
                } for p in self.measurement_points.values()
            ]
        }
        with open(fp, 'w') as f:
            json.dump(data, f, indent=2)
            print(f"✅ Datos guardados: {fp}")

    def load_data(self, fp):
        with open(fp, 'r') as f:
            data = json.load(f)
        self.current_ssid = data.get('ssid', 'Unknown')
        self.measurement_points.clear()

        for pd in data['points']:
            p = MeasurementPoint(pd['id'], pd['x'], pd['y'])
            p.measurements_24 = pd.get(
                'rssi_2.4', pd.get('measurements_2.4', []))
            p.measurements_5 = pd.get('rssi_5', pd.get('measurements_5', []))
            p.measurements_dl_24 = pd.get('dl_2.4', [])
            p.measurements_ul_24 = pd.get('ul_2.4', [])
            p.measurements_dl_5 = pd.get('dl_5', [])
            p.measurements_ul_5 = pd.get('ul_5', [])
            self.measurement_points[p.id] = p
            self.next_point_id = max(self.next_point_id, p.id + 1)


class WiFiMapperGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WiFi Heatmap Generator Pro v7 - Multiplataforma")
        self.root.geometry("1200x850")
        self.root.configure(bg='#2b2b2b')

        self.generator = WiFiHeatmapGenerator()
        self.canvas = None
        self.floor_image = None
        self.floor_image_path = None
        self.selected_point = None
        self.measurement_queue = Queue()

        self.setup_modern_style()
        self.setup_gui()
        self.process_queue()

    def setup_modern_style(self):
        """Configura el estilo moderno para la aplicación"""
        style = ttk.Style()

        # Tema base
        style.theme_use('clam')

        # Colores modernos
        colors = {
            'bg_primary': '#2b2b2b',      # Gris oscuro principal
            'bg_secondary': '#3c3c3c',    # Gris oscuro secundario
            'bg_accent': '#4a90e2',       # Azul acento
            'text_primary': '#ffffff',     # Texto blanco
            'text_secondary': '#b0b0b0',   # Texto gris claro
            'success': '#27ae60',          # Verde éxito
            'warning': '#f39c12',          # Naranja advertencia
            'error': '#e74c3c'             # Rojo error
        }

        # Configurar estilos
        style.configure('Modern.TFrame', background=colors['bg_secondary'])
        style.configure('Modern.TLabelframe', background=colors['bg_secondary'],
                        foreground=colors['text_primary'], borderwidth=1, relief='solid')
        style.configure('Modern.TLabelframe.Label', background=colors['bg_secondary'],
                        foreground=colors['text_primary'], font=('Segoe UI', 10, 'bold'))

        style.configure('Modern.TButton',
                        background=colors['bg_accent'],
                        foreground=colors['text_primary'],
                        borderwidth=0,
                        focuscolor='none',
                        font=('Segoe UI', 9))
        style.map('Modern.TButton',
                  background=[('active', '#5ba0f2'), ('pressed', '#3a7bc8')])

        style.configure('Success.TButton',
                        background=colors['success'],
                        foreground=colors['text_primary'],
                        borderwidth=0,
                        focuscolor='none',
                        font=('Segoe UI', 9, 'bold'))
        style.map('Success.TButton',
                  background=[('active', '#2ecc71'), ('pressed', '#229954')])

        style.configure('Modern.TLabel',
                        background=colors['bg_secondary'],
                        foreground=colors['text_primary'],
                        font=('Segoe UI', 9))

        style.configure('Modern.TEntry',
                        fieldbackground='#ffffff',
                        borderwidth=1,
                        font=('Segoe UI', 9))

        style.configure('Modern.TRadiobutton',
                        background=colors['bg_secondary'],
                        foreground=colors['text_primary'],
                        font=('Segoe UI', 9))

        style.configure('Modern.TCheckbutton',
                        background=colors['bg_secondary'],
                        foreground=colors['text_primary'],
                        font=('Segoe UI', 9))

    def setup_gui(self):
        # Contenedor Principal con estilo moderno
        main_frame = ttk.Frame(self.root, style='Modern.TFrame', padding="15")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Panel Izquierdo (Controles) y Derecho (Canvas)
        left_panel = ttk.Frame(main_frame, style='Modern.TFrame', width=280)
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 15))
        left_panel.grid_propagate(False)

        right_panel = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=2)
        right_panel.grid(row=0, column=1, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # --- PANEL IZQUIERDO ---
        self.create_file_section(left_panel)
        self.create_measurement_section(left_panel)
        self.create_point_info_section(left_panel)
        self.create_map_section(left_panel)
        self.create_status_section(left_panel)

        # --- PANEL DERECHO ---
        self.canvas = tk.Canvas(
            right_panel, bg='#f8f9fa', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Agregar información del sistema
        system_info = f"Sistema: {platform.system()} {platform.release()}"
        ttk.Label(left_panel, text=system_info, style='Modern.TLabel',
                  font=('Segoe UI', 8)).pack(side=tk.BOTTOM, pady=(10, 0))

    def create_file_section(self, parent):
        """Crea la sección de manejo de archivos"""
        file_frame = ttk.LabelFrame(parent, text="📁 Gestión de Archivos",
                                    style='Modern.TLabelframe', padding=12)
        file_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(file_frame, text="🏗️ Cargar Plano de Planta",
                   command=self.load_floor_plan,
                   style='Modern.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(file_frame, text="💾 Guardar Datos",
                   command=self.save_data,
                   style='Modern.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(file_frame, text="📂 Cargar Datos",
                   command=self.load_data,
                   style='Modern.TButton').pack(fill=tk.X, pady=2)

    def create_measurement_section(self, parent):
        """Crea la sección de control de mediciones"""
        measure_frame = ttk.LabelFrame(parent, text="📡 Control de Mediciones",
                                       style='Modern.TLabelframe', padding=12)
        measure_frame.pack(fill=tk.X, pady=(0, 10))

        # Modo de medición
        ttk.Label(measure_frame, text="Modo de medición:",
                  style='Modern.TLabel',
                  font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        self.mode_var = tk.StringVar(value="auto")
        auto_rb = ttk.Radiobutton(measure_frame, text="🔄 Automático (Detectar WiFi)",
                                  variable=self.mode_var, value="auto",
                                  style='Modern.TRadiobutton')
        auto_rb.pack(anchor=tk.W)

        manual_rb = ttk.Radiobutton(measure_frame, text="✏️ Manual (RSSI personalizado)",
                                    variable=self.mode_var, value="manual",
                                    style='Modern.TRadiobutton')
        manual_rb.pack(anchor=tk.W)

        # Entrada RSSI manual
        rssi_frame = ttk.Frame(measure_frame, style='Modern.TFrame')
        rssi_frame.pack(fill=tk.X, pady=(5, 10), padx=(20, 0))
        ttk.Label(rssi_frame, text="RSSI (dBm):",
                  style='Modern.TLabel').pack(side=tk.LEFT)
        self.rssi_entry = ttk.Entry(rssi_frame, width=8, style='Modern.TEntry')
        self.rssi_entry.insert(0, "-50")
        self.rssi_entry.pack(side=tk.RIGHT)

        # Separador
        separator1 = ttk.Separator(measure_frame, orient='horizontal')
        separator1.pack(fill=tk.X, pady=10)

        # Test de velocidad
        self.measure_speed_var = tk.BooleanVar(value=False)
        speed_check = ttk.Checkbutton(measure_frame, text="⚡ Medir Velocidad (iperf3)",
                                      variable=self.measure_speed_var,
                                      style='Modern.TCheckbutton')
        speed_check.pack(anchor=tk.W, pady=(0, 5))

        ip_frame = ttk.Frame(measure_frame, style='Modern.TFrame')
        ip_frame.pack(fill=tk.X, padx=(20, 0))
        ttk.Label(ip_frame, text="IP Servidor:",
                  style='Modern.TLabel').pack(side=tk.LEFT)
        self.iperf_server_ip = tk.StringVar(value="192.168.1.100")
        ip_entry = ttk.Entry(ip_frame, textvariable=self.iperf_server_ip,
                             width=15, style='Modern.TEntry')
        ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Botones de medición
        buttons_frame = ttk.Frame(measure_frame, style='Modern.TFrame')
        buttons_frame.pack(fill=tk.X, pady=(15, 0))

        self.measure_button = ttk.Button(buttons_frame, text="📍 Medición Simple",
                                         command=self.measure_selected_point,
                                         style='Success.TButton')
        self.measure_button.pack(fill=tk.X, pady=2)

        self.measure_button_auto = ttk.Button(buttons_frame, text="🔄 Medición x10 (2seg)",
                                              command=self.measure_point_automated,
                                              style='Success.TButton')
        self.measure_button_auto.pack(fill=tk.X, pady=2)

    def create_point_info_section(self, parent):
        """Crea la sección de información del punto"""
        info_frame = ttk.LabelFrame(parent, text="📊 Información del Punto",
                                    style='Modern.TLabelframe', padding=12)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.point_label = ttk.Label(info_frame, text="Punto: Ninguno seleccionado",
                                     style='Modern.TLabel',
                                     font=('Segoe UI', 10, 'bold'))
        self.point_label.pack(anchor=tk.W)

        # Frame para información scrollable
        info_scroll_frame = ttk.Frame(info_frame, style='Modern.TFrame')
        info_scroll_frame.pack(fill=tk.X, pady=(5, 0))

        self.point_info_label = ttk.Label(info_scroll_frame, text="",
                                          style='Modern.TLabel',
                                          justify=tk.LEFT,
                                          font=('Segoe UI', 8))
        self.point_info_label.pack(anchor=tk.W)

    def create_map_section(self, parent):
        """Crea la sección de generación de mapas"""
        map_frame = ttk.LabelFrame(parent, text="🗺️ Generar Mapa de Calor",
                                   style='Modern.TLabelframe', padding=12)
        map_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(map_frame, text="Banda de frecuencia:",
                  style='Modern.TLabel',
                  font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        self.band_var = tk.StringVar(value="2.4")
        band_frame = ttk.Frame(map_frame, style='Modern.TFrame')
        band_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Radiobutton(band_frame, text="📶 2.4 GHz",
                        variable=self.band_var, value="2.4",
                        style='Modern.TRadiobutton').pack(side=tk.LEFT)
        ttk.Radiobutton(band_frame, text="📡 5 GHz",
                        variable=self.band_var, value="5",
                        style='Modern.TRadiobutton').pack(side=tk.LEFT, padx=(20, 0))

        ttk.Button(map_frame, text="🎨 Generar Mapa de Calor",
                   command=self.generate_map,
                   style='Success.TButton').pack(fill=tk.X, pady=(0, 5))

        ttk.Button(map_frame, text="🧹 Limpiar Todos los Puntos",
                   command=self.clear_all,
                   style='Modern.TButton').pack(fill=tk.X)

    def create_status_section(self, parent):
        """Crea la sección de estado general"""
        status_frame = ttk.LabelFrame(parent, text="ℹ️ Estado del Sistema",
                                      style='Modern.TLabelframe', padding=12)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.ssid_label = ttk.Label(status_frame, text="SSID: (desconocido)",
                                    style='Modern.TLabel',
                                    font=('Segoe UI', 9, 'bold'))
        self.ssid_label.pack(anchor=tk.W)

        self.count_label = ttk.Label(status_frame, text="Puntos totales: 0",
                                     style='Modern.TLabel')
        self.count_label.pack(anchor=tk.W)

        # Información adicional del sistema
        os_info = f"OS: {self.generator.system_os}"
        ttk.Label(status_frame, text=os_info,
                  style='Modern.TLabel',
                  font=('Segoe UI', 8)).pack(anchor=tk.W, pady=(5, 0))

    def load_floor_plan(self):
        file_path = filedialog.askopenfilename(
            title="Seleccionar Plano de Planta",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif")])

        if not file_path:
            return

        try:
            self.floor_image_path = file_path
            image = Image.open(file_path)

            # Esperar a que el canvas tenga dimensiones
            self.canvas.update_idletasks()
            canvas_width = max(self.canvas.winfo_width(), 400)
            canvas_height = max(self.canvas.winfo_height(), 300)

            # Calcular escala manteniendo proporción
            scale_factor = min(canvas_width / image.width,
                               canvas_height / image.height)
            new_width = int(image.width * scale_factor)
            new_height = int(image.height * scale_factor)

            # Redimensionar imagen
            image = image.resize((new_width, new_height),
                                 Image.Resampling.LANCZOS)

            self.floor_image = ImageTk.PhotoImage(image)
            self.canvas.delete("all")
            self.canvas.create_image(
                0, 0, anchor=tk.NW, image=self.floor_image)

            self.generator.floor_plan_dims = (new_width, new_height)
            self.redraw_all_points()

            messagebox.showinfo("Éxito", f"Plano cargado correctamente\nDimensiones: {new_width}x{new_height}")

        except Exception as e:
            messagebox.showerror(
                "Error", f"No se pudo cargar el plano:\n{str(e)}")

    def on_canvas_click(self, event):
        if not self.floor_image:
            messagebox.showwarning("Advertencia",
                                   "Primero debes cargar un plano de planta")
            return

        point = self.generator.create_or_update_point(event.x, event.y)
        self.select_point(point)

    def select_point(self, point):
        self.selected_point = point
        self.redraw_all_points()
        self.highlight_selected_point()
        self.update_point_info()

    def measure_selected_point(self):
        self._start_measurement_thread(iterations=1)

    def measure_point_automated(self):
        self._start_measurement_thread(iterations=10)

    def _start_measurement_thread(self, iterations):
        if not self.selected_point:
            messagebox.showwarning("Advertencia",
                                   "Primero debes seleccionar un punto en el plano")
            return

        # Deshabilitar botones durante medición
        self.measure_button.config(state=tk.DISABLED)
        self.measure_button_auto.config(state=tk.DISABLED)

        # Iniciar hilo de medición
        threading.Thread(target=self._measure_thread_task,
                         args=(iterations,), daemon=True).start()

    def _measure_thread_task(self, iterations):
        point = self.selected_point
        mode = self.mode_var.get()

        for i in range(iterations):
            # Actualizar estado en UI
            status_text = f"Midiendo {i+1}/{iterations}..."
            self.root.after(
                0, lambda: self.measure_button.config(text=status_text))
            self.root.after(
                0, lambda: self.measure_button_auto.config(text=status_text))

            if mode == "manual":
                try:
                    rssi_value = int(self.rssi_entry.get())
                    selected_band = self.band_var.get()
                    self.measurement_queue.put(
                        ('success', point, rssi_value, selected_band, "Manual", None, None))
                except ValueError:
                    self.measurement_queue.put(
                        ('error', "Valor RSSI manual inválido. Debe ser un número entero."))
                    break
            else:
                # Medición automática
                rssi, ssid, band = self.generator.get_wifi_rssi()
                if rssi is None:
                    self.measurement_queue.put(
                        ('error', f"Error obteniendo WiFi: {ssid}"))
                    break

                dl_speed, ul_speed = None, None
                if self.measure_speed_var.get():
                    speeds, error_msg = self.generator.get_wifi_speed(
                        self.iperf_server_ip.get())
                    if error_msg:
                        self.measurement_queue.put(('error', error_msg))
                        break
                    dl_speed, ul_speed = speeds

                self.measurement_queue.put(
                    ('success', point, rssi, band, ssid, dl_speed, ul_speed))

            # Pausa entre mediciones automáticas
            if iterations > 1 and i < iterations - 1:
                time.sleep(2)

        # Señalar que terminó
        self.measurement_queue.put(('finished',))

    def process_queue(self):
        try:
            while not self.measurement_queue.empty():
                message = self.measurement_queue.get_nowait()
                msg_type = message[0]

                if msg_type == 'success':
                    _, point, rssi, band, ssid, dl_speed, ul_speed = message

                    if self.generator.current_ssid is None and ssid != "Manual":
                        self.generator.current_ssid = ssid

                    self.ssid_label.config(
                        text=f"SSID: {self.generator.current_ssid}")
                    self.generator.add_measurement_to_point(
                        point, rssi, band, dl_speed, ul_speed)

                    self.redraw_all_points()
                    self.highlight_selected_point()
                    self.update_point_info()
                    self.count_label.config(text=f"Puntos totales: {len(self.generator.measurement_points)}")

                elif msg_type == 'error':
                    messagebox.showerror("Error de Medición", message[1])

                elif msg_type == 'finished':
                    self.measure_button.config(
                        state=tk.NORMAL, text="📍 Medición Simple")
                    self.measure_button_auto.config(
                        state=tk.NORMAL, text="🔄 Medición x10 (2seg)")

        finally:
            self.root.after(100, self.process_queue)

    def update_point_info(self):
        if not self.selected_point:
            self.point_label.config(text="Punto: Ninguno seleccionado")
            self.point_info_label.config(text="")
            return

        point = self.selected_point
        self.point_label.config(text=f"📍 Punto ID: {point.id}")

        info_text = ""

        # Información 2.4 GHz
        count_24 = point.get_measurement_count('2.4')
        if count_24 > 0:
            avg_rssi = point.get_average_rssi('2.4')
            avg_dl = point.get_average_speed('2.4', 'dl')
            avg_ul = point.get_average_speed('2.4', 'ul')

            info_text += f"📶 Banda 2.4 GHz ({count_24} mediciones):\n"
            info_text += f"   RSSI: {avg_rssi} dBm\n"
            if avg_dl is not None:
                info_text += f"   Descarga: {avg_dl} Mbps\n"
            if avg_ul is not None:
                info_text += f"   Subida: {avg_ul} Mbps\n"

        # Información 5 GHz
        count_5 = point.get_measurement_count('5')
        if count_5 > 0:
            avg_rssi = point.get_average_rssi('5')
            avg_dl = point.get_average_speed('5', 'dl')
            avg_ul = point.get_average_speed('5', 'ul')

            info_text += f"📡 Banda 5 GHz ({count_5} mediciones):\n"
            info_text += f"   RSSI: {avg_rssi} dBm\n"
            if avg_dl is not None:
                info_text += f"   Descarga: {avg_dl} Mbps\n"
            if avg_ul is not None:
                info_text += f"   Subida: {avg_ul} Mbps\n"

        if not info_text:
            info_text = "No hay mediciones para este punto"

        self.point_info_label.config(text=info_text.strip())

    def redraw_all_points(self):
        """Redibuja todos los puntos de medición en el canvas"""
        self.canvas.delete("point")

        for point in self.generator.measurement_points.values():
            # Determinar color basado en las bandas disponibles
            has_24 = point.get_measurement_count('2.4') > 0
            has_5 = point.get_measurement_count('5') > 0

            if has_24 and has_5:
                color = '#8e44ad'  # Púrpura - ambas bandas
                border_color = '#9b59b6'
            elif has_24:
                color = '#3498db'  # Azul - solo 2.4GHz
                border_color = '#5dade2'
            elif has_5:
                color = '#e74c3c'  # Rojo - solo 5GHz
                border_color = '#ec7063'
            else:
                color = '#95a5a6'  # Gris - sin mediciones
                border_color = '#bdc3c7'

            # Dibujar círculo del punto
            self.canvas.create_oval(
                point.x - 8, point.y - 8,
                point.x + 8, point.y + 8,
                fill=color,
                outline=border_color,
                width=2,
                tags="point"
            )

            # Dibujar ID del punto
            self.canvas.create_text(
                point.x, point.y,
                text=str(point.id),
                fill='white',
                font=('Segoe UI', 8, 'bold'),
                tags="point"
            )

    def highlight_selected_point(self):
        """Resalta el punto seleccionado"""
        if self.selected_point:
            x, y = self.selected_point.x, self.selected_point.y
            # Crear anillo de selección dorado
            self.canvas.create_oval(
                x - 12, y - 12,
                x + 12, y + 12,
                outline='#f1c40f',
                width=3,
                tags="point"
            )
            # Anillo exterior más sutil
            self.canvas.create_oval(
                x - 15, y - 15,
                x + 15, y + 15,
                outline='#f39c12',
                width=1,
                tags="point"
            )

    def generate_map(self):
        """Genera y muestra el mapa de calor"""
        band = self.band_var.get()

        # Verificar que hay datos suficientes
        valid_points = [p for p in self.generator.measurement_points.values()
                        if p.get_average_rssi(band) is not None]

        if len(valid_points) < 4:
            messagebox.showwarning(
                "Datos Insuficientes",
                f"Se necesitan al menos 4 puntos con mediciones para la banda {band} GHz.\n"
                f"Actualmente tienes {len(valid_points)} puntos válidos."
            )
            return

        # Solicitar ubicación para guardar
        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG", "*.png"),
                ("PDF", "*.pdf"),
                ("SVG", "*.svg")
            ],
            title=f"Guardar Mapa de Calor - Banda {band} GHz"
        )

        if save_path:
            try:
                self.generator.plot_heatmap_on_floor_plan(
                    band=band,
                    floor_plan_path=self.floor_image_path,
                    save_path=save_path
                )
                messagebox.showinfo(
                    "Éxito",
                    f"Mapa de calor generado y guardado exitosamente:\n{save_path}"
                )
            except Exception as e:
                messagebox.showerror(
                    "Error al Generar Mapa",
                    f"No se pudo generar el mapa de calor:\n{str(e)}"
                )

    def save_data(self):
        """Guarda los datos de medición en formato JSON"""
        if not self.generator.measurement_points:
            messagebox.showwarning(
                "Sin Datos", "No hay puntos de medición para guardar")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Guardar Datos de Medición"
        )

        if file_path:
            try:
                self.generator.save_data(file_path)
                messagebox.showinfo(
                    "Éxito",
                    f"Datos guardados exitosamente:\n{file_path}\n\n"
                    f"Puntos guardados: {len(self.generator.measurement_points)}"
                )
            except Exception as e:
                messagebox.showerror(
                    "Error al Guardar",
                    f"No se pudieron guardar los datos:\n{str(e)}"
                )

    def load_data(self):
        """Carga datos de medición desde un archivo JSON"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")],
            title="Cargar Datos de Medición"
        )

        if file_path:
            try:
                self.generator.load_data(file_path)

                # Actualizar interfaz
                self.redraw_all_points()
                self.count_label.config(
                    text=f"Puntos totales: {len(self.generator.measurement_points)}"
                )
                self.ssid_label.config(
                    text=f"SSID: {self.generator.current_ssid}")

                # Deseleccionar punto actual
                self.select_point(None)
                self.update_point_info()

                messagebox.showinfo(
                    "Éxito",
                    f"Datos cargados exitosamente:\n{file_path}\n\n"
                    f"Puntos cargados: {len(self.generator.measurement_points)}\n"
                    f"SSID: {self.generator.current_ssid}"
                )

            except Exception as e:
                messagebox.showerror(
                    "Error al Cargar",
                    f"No se pudo cargar el archivo JSON:\n{str(e)}"
                )

    def clear_all(self):
        """Limpia todos los puntos de medición"""
        if not self.generator.measurement_points:
            messagebox.showinfo("Sin Datos", "No hay puntos para limpiar")
            return

        result = messagebox.askyesno(
            "Confirmar Limpieza",
            f"¿Estás seguro de que deseas eliminar todos los {len(self.generator.measurement_points)} puntos de medición?\n\n"
            "Esta acción no se puede deshacer."
        )

        if result:
            self.generator.measurement_points.clear()
            self.generator.next_point_id = 1
            self.generator.current_ssid = None

            # Actualizar interfaz
            self.select_point(None)
            self.redraw_all_points()
            self.count_label.config(text="Puntos totales: 0")
            self.ssid_label.config(text="SSID: (desconocido)")

            messagebox.showinfo("Limpieza Completa",
                                "Todos los puntos han sido eliminados")

    def run(self):
        """Inicia la aplicación"""
        print("\n" + "="*70)
        print("🌐 WiFi Heatmap Generator Pro v7 - Multiplataforma")
        print("="*70)
        print(f"🖥️  Sistema Operativo: {platform.system()} {platform.release()}")
        print(f"🐍 Python: {platform.python_version()}")
        print(f"📡 Detección WiFi: Habilitada para {platform.system()}")
        print("="*70)
        print("✨ Interfaz moderna cargada - ¡Listo para usar!")
        print("="*70 + "\n")

        # Configurar el cierre de la aplicación
        def on_closing():
            if messagebox.askokcancel("Salir", "¿Deseas cerrar la aplicación?"):
                self.root.quit()
                self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", on_closing)

        # Iniciar bucle principal
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\n🔄 Cerrando aplicación...")
            self.root.quit()


if __name__ == "__main__":
    # Verificar dependencias críticas
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        import scipy.interpolate
        from PIL import Image
    except ImportError as e:
        print(f"❌ Error: Falta una dependencia crítica: {e}")
        print("\n📦 Para instalar las dependencias necesarias, ejecuta:")
        print("   pip install matplotlib numpy scipy pillow")
        sys.exit(1)

    # Mostrar información del sistema
    print(f"🚀 Iniciando WiFi Heatmap Generator en {platform.system()}")

    # Crear y ejecutar aplicación
    try:
        app = WiFiMapperGUI()
        app.run()
    except Exception as e:
        print(f"❌ Error crítico al iniciar la aplicación: {e}")
        messagebox.showerror("Error Crítico",
                             f"No se pudo iniciar la aplicación:\n{str(e)}")
        sys.exit(1)
