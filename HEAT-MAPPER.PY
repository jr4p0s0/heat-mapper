#!/usr/bin/env python3
"""
WiFi Heatmap Generator Pro - Actualización con mapas de velocidad mejorados
- AÑADIDO: Seaborn para mejores paletas de colores
- MEJORADO: Mapas de velocidad combinados (descarga + subida) en una sola imagen
- SIMPLIFICADO: Interfaz con un solo botón para mapas de velocidad
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
import iperf3
import seaborn as sns  # NUEVO: Importar seaborn para mejores colores

# Configurar seaborn
sns.set_style("whitegrid")


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
            result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                                    capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                output = result.stdout
                ssid_match = re.search(
                    r'^\s*SSID\s*:\s*(.+)', output, re.MULTILINE)
                signal_match = re.search(
                    r'^\s*Signal\s*:\s*(\d+)%', output, re.MULTILINE)
                channel_match = re.search(
                    r'^\s*Channel\s*:\s*(\d+)', output, re.MULTILINE)

                if ssid_match and signal_match:
                    ssid = ssid_match.group(1).strip()
                    signal_percent = int(signal_match.group(1))
                    rssi = int((signal_percent / 2) - 100)
                    band = '2.4'
                    if channel_match:
                        channel = int(channel_match.group(1))
                        band = '5' if channel > 14 else '2.4'
                    return rssi, ssid, band
        except Exception as e:
            print(f"-> Método netsh Windows falló: {e}")

        try:
            result = subprocess.run(['wmic', 'path', 'win32_networkadapter', 'where',
                                     'NetConnectionStatus=2', 'get', 'Name,NetConnectionID'],
                                    capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                return -50, "Red WiFi Activa", "2.4"
        except Exception as e:
            print(f"-> Método wmic Windows falló: {e}")

        return None, "No se pudo obtener información WiFi en Windows", None

    def _get_wifi_rssi_linux(self):
        """Métodos específicos para Linux"""
        try:
            result = subprocess.run(
                ['iwconfig'], capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                output = result.stdout
                wifi_interfaces = re.findall(
                    r'^(\w+)\s+IEEE 802\.11', output, re.MULTILINE)

                for interface in wifi_interfaces:
                    iface_result = subprocess.run(['iwconfig', interface],
                                                  capture_output=True, text=True, timeout=5, check=False)
                    if iface_result.returncode == 0:
                        iface_output = iface_result.stdout
                        ssid_match = re.search(
                            r'ESSID:"([^"]+)"', iface_output)
                        signal_match = re.search(
                            r'Signal level=(-?\d+)', iface_output)
                        freq_match = re.search(
                            r'Frequency:([\d.]+)', iface_output)

                        if ssid_match and signal_match:
                            ssid = ssid_match.group(1)
                            rssi = int(signal_match.group(1))
                            band = '2.4'
                            if freq_match:
                                freq = float(freq_match.group(1))
                                band = '5' if freq > 4 else '2.4'
                            return rssi, ssid, band
        except Exception as e:
            print(f"-> Método iwconfig Linux falló: {e}")

        try:
            result = subprocess.run(
                ['iw', 'dev'], capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                interfaces = re.findall(r'Interface (\w+)', result.stdout)

                for interface in interfaces:
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
                                band = '2.4'
                                if freq_match:
                                    freq_mhz = int(freq_match.group(1))
                                    band = '5' if freq_mhz > 4000 else '2.4'
                                return rssi, ssid, band
        except Exception as e:
            print(f"-> Método iw Linux falló: {e}")

        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL,FREQ', 'dev', 'wifi'],
                                    capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split(':')
                    if len(parts) >= 4 and parts[0] == 'yes':
                        ssid = parts[1]
                        signal_percent = parts[2]
                        freq = parts[3] if parts[3] else '2400'

                        if signal_percent.isdigit():
                            rssi = int((int(signal_percent) / 2) - 100)
                            band = '5' if int(freq) > 4000 else '2.4'
                            return rssi, ssid, band
        except Exception as e:
            print(f"-> Método nmcli Linux falló: {e}")

        try:
            with open('/proc/net/wireless', 'r') as f:
                lines = f.readlines()
                if len(lines) > 2:
                    for line in lines[2:]:
                        parts = line.split()
                        if len(parts) >= 3:
                            interface = parts[0].rstrip(':')
                            signal_quality = parts[2]

                            try:
                                iwconfig_result = subprocess.run(['iwconfig', interface],
                                                                 capture_output=True, text=True, timeout=3)
                                if iwconfig_result.returncode == 0:
                                    ssid_match = re.search(
                                        r'ESSID:"([^"]+)"', iwconfig_result.stdout)
                                    if ssid_match:
                                        ssid = ssid_match.group(1)
                                        rssi = int(float(signal_quality)) - 100
                                        return rssi, ssid, '2.4'
                            except:
                                pass
        except Exception as e:
            print(f"-> Método /proc/net/wireless Linux falló: {e}")

        return None, "No se pudo obtener información WiFi en Linux", None
    
    def get_wifi_speed(self, server_ip):
        """Ejecuta iperf3 usando la librería de Python para obtener velocidad."""
        dl_mbps, ul_mbps = None, None
        
        try:
            print(f"Ejecutando iperf3 (descarga) contra el servidor {server_ip}...")
            client = iperf3.Client()
            client.server_hostname = server_ip
            client.port = 5201
            client.duration = 5
            client.protocol = 'tcp'
            client.reverse = True
            
            result_dl = client.run()
            
            if result_dl.error:
                return None, f"Error en test de descarga: {result_dl.error}"
            
            dl_mbps = round(result_dl.received_Mbps, 2)
            print(f"-> Velocidad de Descarga: {dl_mbps} Mbps")
            
            print(f"Ejecutando iperf3 (subida) contra el servidor {server_ip}...")
            client2 = iperf3.Client()
            client2.server_hostname = server_ip
            client2.port = 5201
            client2.duration = 5
            client2.protocol = 'tcp'
            client2.reverse = False
            
            result_ul = client2.run()
            
            if result_ul.error:
                return None, f"Error en test de subida: {result_ul.error}"
            
            ul_mbps = round(result_ul.sent_Mbps, 2)
            print(f"-> Velocidad de Subida: {ul_mbps} Mbps")
            
        except Exception as e:
            error_msg = str(e)
            if "Connection refused" in error_msg:
                return None, "Error: No se puede conectar al servidor iperf3."
            elif "No route to host" in error_msg:
                return None, "Error: No se puede alcanzar el servidor."
            elif "timed out" in error_msg or "timeout" in error_msg.lower():
                return None, "Error: Tiempo de espera agotado."
            else:
                return None, f"Error inesperado: {error_msg}"
        
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
        print(f"  -> Promedios ({count}x): RSSI: {avg_rssi}dBm | DL: {avg_dl} Mbps | UL: {avg_ul} Mbps")

    def generate_heatmap_data(self, band, data_type='rssi', speed_direction='dl', resolution=100):
        """Genera datos de mapa de calor para RSSI o velocidad."""
        if data_type == 'rssi':
            valid_points = [p for p in self.measurement_points.values() 
                        if p.get_average_rssi(band) is not None]
            if len(valid_points) < 4:
                raise ValueError(f"Se necesitan al menos 4 puntos con RSSI para la banda {band} GHz.")
            values = np.array([p.get_average_rssi(band) for p in valid_points])
        else:
            valid_points = [p for p in self.measurement_points.values() 
                        if p.get_average_speed(band, speed_direction) is not None]
            if len(valid_points) < 4:
                raise ValueError(f"Se necesitan al menos 4 puntos con velocidad para la banda {band} GHz.")
            values = np.array([p.get_average_speed(band, speed_direction) for p in valid_points])
        
        points = np.array([[p.x, p.y] for p in valid_points])
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

            ax.set_title(f'Mapa de Calor WiFi - Banda {band} GHz\nSSID: {self.current_ssid}', 
                        fontsize=14, weight='bold')
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

    def plot_combined_speed_heatmaps(self, band, floor_plan_path=None, save_path=None):
        """
        NUEVO: Genera mapas de calor combinados (descarga y subida) en una sola imagen.
        Usa seaborn para mejores paletas de colores.
        """
        # Crear figura con 2 subplots lado a lado
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 9))
        fig.patch.set_facecolor('#f5f5f5')
        
        # Paletas de seaborn más distintivas
        cmap_download = sns.color_palette("rocket_r", as_cmap=True)  # Para descarga
        cmap_upload = sns.color_palette("mako_r", as_cmap=True)  # Para subida
        
        # Cargar imagen de fondo si existe
        floor_img = None
        if floor_plan_path and os.path.exists(floor_plan_path):
            floor_img = plt.imread(floor_plan_path)
        
        # === MAPA DE DESCARGA (IZQUIERDA) ===
        if floor_img is not None:
            ax1.imshow(floor_img, extent=[0, self.floor_plan_dims[0], 
                                          self.floor_plan_dims[1], 0], aspect='auto', alpha=0.7)
        
        try:
            xi_dl, yi_dl, zi_dl = self.generate_heatmap_data(band, data_type='speed', 
                                                             speed_direction='dl')
            
            # Determinar rango de valores
            vmax_dl = 300 if band == '5' else 100
            
            # Crear contornos con la paleta de seaborn
            im1 = ax1.contourf(xi_dl, yi_dl, zi_dl, levels=20, 
                              cmap=cmap_download, vmin=0, vmax=vmax_dl, alpha=0.7)
            
            # Dibujar puntos de medición
            for p in self.measurement_points.values():
                speed_val = p.get_average_speed(band, 'dl')
                if speed_val is not None:
                    ax1.plot(p.x, p.y, 'o', color='white', markersize=12, 
                            markeredgecolor='black', markeredgewidth=2.5)
                    ax1.text(p.x, p.y, str(p.id), fontsize=10, ha='center', 
                            va='center', color='black', weight='bold')
            
            ax1.set_title(f'Velocidad de Descarga\nBanda {band} GHz', 
                         fontsize=16, weight='bold', pad=15)
            ax1.set_xlabel('Posición X (píxeles)', fontsize=12)
            ax1.set_ylabel('Posición Y (píxeles)', fontsize=12)
            ax1.set_xlim(0, self.floor_plan_dims[0])
            ax1.set_ylim(self.floor_plan_dims[1], 0)
            
            # Barra de colores para descarga
            cbar1 = plt.colorbar(im1, ax=ax1, orientation='vertical', pad=0.02, shrink=0.8)
            cbar1.set_label('Velocidad (Mbps)', fontsize=12, weight='bold')
            cbar1.ax.tick_params(labelsize=10)
            ax1.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
            
        except ValueError as e:
            ax1.text(0.5, 0.5, f'Datos de descarga insuficientes\n{str(e)}',
                    ha='center', va='center', transform=ax1.transAxes, 
                    fontsize=12, color='red', weight='bold')
            ax1.set_title(f'Descarga - Banda {band} GHz - Error', fontsize=14)
        
        # === MAPA DE SUBIDA (DERECHA) ===
        if floor_img is not None:
            ax2.imshow(floor_img, extent=[0, self.floor_plan_dims[0], 
                                          self.floor_plan_dims[1], 0], aspect='auto', alpha=0.7)
        
        try:
            xi_ul, yi_ul, zi_ul = self.generate_heatmap_data(band, data_type='speed', 
                                                             speed_direction='ul')
            
            # Determinar rango de valores (generalmente la subida es más baja)
            vmax_ul = 100 if band == '5' else 50
            
            # Crear contornos con la paleta de seaborn
            im2 = ax2.contourf(xi_ul, yi_ul, zi_ul, levels=20, 
                              cmap=cmap_upload, vmin=0, vmax=vmax_ul, alpha=0.7)
            
            # Dibujar puntos de medición
            for p in self.measurement_points.values():
                speed_val = p.get_average_speed(band, 'ul')
                if speed_val is not None:
                    ax2.plot(p.x, p.y, 'o', color='white', markersize=12, 
                            markeredgecolor='black', markeredgewidth=2.5)
                    ax2.text(p.x, p.y, str(p.id), fontsize=10, ha='center', 
                            va='center', color='black', weight='bold')
            
            ax2.set_title(f'Velocidad de Subida\nBanda {band} GHz', 
                         fontsize=16, weight='bold', pad=15)
            ax2.set_xlabel('Posición X (píxeles)', fontsize=12)
            ax2.set_ylabel('Posición Y (píxeles)', fontsize=12)
            ax2.set_xlim(0, self.floor_plan_dims[0])
            ax2.set_ylim(self.floor_plan_dims[1], 0)
            
            # Barra de colores para subida
            cbar2 = plt.colorbar(im2, ax=ax2, orientation='vertical', pad=0.02, shrink=0.8)
            cbar2.set_label('Velocidad (Mbps)', fontsize=12, weight='bold')
            cbar2.ax.tick_params(labelsize=10)
            ax2.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
            
        except ValueError as e:
            ax2.text(0.5, 0.5, f'Datos de subida insuficientes\n{str(e)}',
                    ha='center', va='center', transform=ax2.transAxes, 
                    fontsize=12, color='red', weight='bold')
            ax2.set_title(f'Subida - Banda {band} GHz - Error', fontsize=14)
        
        # Título general de la figura
        fig.suptitle(f'Mapas de Velocidad WiFi - SSID: {self.current_ssid}', 
                    fontsize=18, weight='bold', y=0.98)
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor='#f5f5f5')
            print(f"✅ Mapas de velocidad combinados guardados: {save_path}")
        
        plt.show()


class WiFiMapperGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WiFi Heatmap Generator Pro v8 - Con Mapas Combinados")
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
        style.theme_use('clam')

        colors = {
            'bg_primary': '#2b2b2b',
            'bg_secondary': '#3c3c3c',
            'bg_accent': '#4a90e2',
            'text_primary': '#ffffff',
            'text_secondary': '#b0b0b0',
            'success': '#27ae60',
            'warning': '#f39c12',
            'error': '#e74c3c'
        }

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
        main_frame = ttk.Frame(self.root, style='Modern.TFrame', padding="15")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(main_frame, style='Modern.TFrame', width=280)
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 15))
        left_panel.grid_propagate(False)

        right_panel = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=2)
        right_panel.grid(row=0, column=1, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self.create_file_section(left_panel)
        self.create_measurement_section(left_panel)
        self.create_point_info_section(left_panel)
        self.create_map_section(left_panel)
        self.create_status_section(left_panel)

        self.canvas = tk.Canvas(right_panel, bg='#f8f9fa', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        system_info = f"Sistema: {platform.system()} {platform.release()}"
        ttk.Label(left_panel, text=system_info, style='Modern.TLabel',
                  font=('Segoe UI', 8)).pack(side=tk.BOTTOM, pady=(10, 0))

    def create_file_section(self, parent):
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
        measure_frame = ttk.LabelFrame(parent, text="📡 Control de Mediciones",
                                       style='Modern.TLabelframe', padding=12)
        measure_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(measure_frame, text="Modo de medición:",
                  style='Modern.TLabel',
                  font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        self.mode_var = tk.StringVar(value="auto")
        ttk.Radiobutton(measure_frame, text="🔄 Automático (Detectar WiFi)",
                                  variable=self.mode_var, value="auto",
                                  style='Modern.TRadiobutton').pack(anchor=tk.W)

        ttk.Radiobutton(measure_frame, text="✏️ Manual (RSSI personalizado)",
                                    variable=self.mode_var, value="manual",
                                    style='Modern.TRadiobutton').pack(anchor=tk.W)

        rssi_frame = ttk.Frame(measure_frame, style='Modern.TFrame')
        rssi_frame.pack(fill=tk.X, pady=(5, 10), padx=(20, 0))
        ttk.Label(rssi_frame, text="RSSI (dBm):",
                  style='Modern.TLabel').pack(side=tk.LEFT)
        self.rssi_entry = ttk.Entry(rssi_frame, width=8, style='Modern.TEntry')
        self.rssi_entry.insert(0, "-50")
        self.rssi_entry.pack(side=tk.RIGHT)

        separator1 = ttk.Separator(measure_frame, orient='horizontal')
        separator1.pack(fill=tk.X, pady=10)

        self.measure_speed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(measure_frame, text="⚡ Medir Velocidad (iperf3)",
                                      variable=self.measure_speed_var,
                                      style='Modern.TCheckbutton').pack(anchor=tk.W, pady=(0, 5))

        ip_frame = ttk.Frame(measure_frame, style='Modern.TFrame')
        ip_frame.pack(fill=tk.X, padx=(20, 0))
        ttk.Label(ip_frame, text="IP Servidor:",
                  style='Modern.TLabel').pack(side=tk.LEFT)
        self.iperf_server_ip = tk.StringVar(value="192.168.1.100")
        ttk.Entry(ip_frame, textvariable=self.iperf_server_ip,
                             width=15, style='Modern.TEntry').pack(side=tk.LEFT, fill=tk.X, expand=True)

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
        info_frame = ttk.LabelFrame(parent, text="📊 Información del Punto",
                                    style='Modern.TLabelframe', padding=12)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.point_label = ttk.Label(info_frame, text="Punto: Ninguno seleccionado",
                                     style='Modern.TLabel',
                                     font=('Segoe UI', 10, 'bold'))
        self.point_label.pack(anchor=tk.W)

        info_scroll_frame = ttk.Frame(info_frame, style='Modern.TFrame')
        info_scroll_frame.pack(fill=tk.X, pady=(5, 0))

        self.point_info_label = ttk.Label(info_scroll_frame, text="",
                                          style='Modern.TLabel',
                                          justify=tk.LEFT,
                                          font=('Segoe UI', 8))
        self.point_info_label.pack(anchor=tk.W)

    def create_map_section(self, parent):
        """ACTUALIZADO: Sección simplificada para mapas de velocidad combinados"""
        map_frame = ttk.LabelFrame(parent, text="🗺️ Generar Mapas de Calor",
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
        
        ttk.Separator(map_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Botón para mapa de RSSI
        ttk.Button(map_frame, text="📊 Generar Mapa de Señal (RSSI)",
                command=self.generate_map,
                style='Success.TButton').pack(fill=tk.X, pady=(0, 10))
        
        ttk.Separator(map_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # NUEVO: Un solo botón para mapas de velocidad combinados
        ttk.Button(map_frame, text="🚀 Generar Mapas de Velocidad\n(⬇️ Descarga + ⬆️ Subida)",
                command=self.generate_combined_speed_maps,
                style='Success.TButton').pack(fill=tk.X, pady=(0, 5))
        
        # Nota informativa
        info_text = "Los mapas de velocidad requieren\nmediciones con iperf3 activado.\nSe generarán ambos mapas juntos."
        ttk.Label(map_frame, text=info_text,
                style='Modern.TLabel',
                font=('Segoe UI', 8),
                foreground='#95a5a6').pack(pady=(5, 10))
        
        ttk.Separator(map_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Button(map_frame, text="Limpiar Todos los Puntos",
                command=self.clear_all,
                style='Modern.TButton').pack(fill=tk.X)

    def generate_combined_speed_maps(self):
        """NUEVO: Genera ambos mapas de velocidad (descarga y subida) en una sola imagen"""
        band = self.band_var.get()
        
        # Verificar que hay datos suficientes para ambos
        valid_dl = [p for p in self.generator.measurement_points.values()
                    if p.get_average_speed(band, 'dl') is not None]
        valid_ul = [p for p in self.generator.measurement_points.values()
                    if p.get_average_speed(band, 'ul') is not None]
        
        if len(valid_dl) < 4 or len(valid_ul) < 4:
            messagebox.showwarning(
                "Datos Insuficientes",
                f"Se necesitan al menos 4 puntos con mediciones de velocidad "
                f"(descarga Y subida) para la banda {band} GHz.\n\n"
                f"Puntos válidos con descarga: {len(valid_dl)}\n"
                f"Puntos válidos con subida: {len(valid_ul)}\n\n"
                f"Asegúrate de:\n"
                f"1. Tener iperf3 activado al medir\n"
                f"2. Tener el servidor iperf3 funcionando\n"
                f"3. Haber realizado mediciones en la banda seleccionada"
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
            title=f"Guardar Mapas de Velocidad Combinados - Banda {band} GHz"
        )
        
        if save_path:
            try:
                self.generator.plot_combined_speed_heatmaps(
                    band=band,
                    floor_plan_path=self.floor_image_path,
                    save_path=save_path
                )
                messagebox.showinfo(
                    "Éxito",
                    f"Mapas de velocidad combinados generados:\n{save_path}"
                )
            except Exception as e:
                messagebox.showerror(
                    "Error al Generar Mapas",
                    f"No se pudieron generar los mapas de velocidad:\n{str(e)}"
                )

    def create_status_section(self, parent):
        status_frame = ttk.LabelFrame(parent, text="Estado del Sistema",
                                      style='Modern.TLabelframe', padding=12)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.ssid_label = ttk.Label(status_frame, text="SSID: (desconocido)",
                                    style='Modern.TLabel',
                                    font=('Segoe UI', 9, 'bold'))
        self.ssid_label.pack(anchor=tk.W)

        self.count_label = ttk.Label(status_frame, text="Puntos totales: 0",
                                     style='Modern.TLabel')
        self.count_label.pack(anchor=tk.W)

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

            self.canvas.update_idletasks()
            canvas_width = max(self.canvas.winfo_width(), 400)
            canvas_height = max(self.canvas.winfo_height(), 300)

            scale_factor = min(canvas_width / image.width,
                               canvas_height / image.height)
            new_width = int(image.width * scale_factor)
            new_height = int(image.height * scale_factor)

            image = image.resize((new_width, new_height),
                                 Image.Resampling.LANCZOS)

            self.floor_image = ImageTk.PhotoImage(image)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.floor_image)

            self.generator.floor_plan_dims = (new_width, new_height)
            self.redraw_all_points()

            messagebox.showinfo("Éxito", f"Plano cargado correctamente\nDimensiones: {new_width}x{new_height}")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el plano:\n{str(e)}")

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

        self.measure_button.config(state=tk.DISABLED)
        self.measure_button_auto.config(state=tk.DISABLED)

        threading.Thread(target=self._measure_thread_task,
                         args=(iterations,), daemon=True).start()

    def _measure_thread_task(self, iterations):
        point = self.selected_point
        mode = self.mode_var.get()

        for i in range(iterations):
            status_text = f"Midiendo {i+1}/{iterations}..."
            self.root.after(0, lambda: self.measure_button.config(text=status_text))
            self.root.after(0, lambda: self.measure_button_auto.config(text=status_text))

            if mode == "manual":
                try:
                    rssi_value = int(self.rssi_entry.get())
                    selected_band = self.band_var.get()
                    self.measurement_queue.put(
                        ('success', point, rssi_value, selected_band, "Manual", None, None))
                except ValueError:
                    self.measurement_queue.put(
                        ('error', "Valor RSSI manual inválido."))
                    break
            else:
                rssi, ssid, band = self.generator.get_wifi_rssi()
                if rssi is None:
                    self.measurement_queue.put(('error', f"Error obteniendo WiFi: {ssid}"))
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

            if iterations > 1 and i < iterations - 1:
                time.sleep(2)

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

                    self.ssid_label.config(text=f"SSID: {self.generator.current_ssid}")
                    self.generator.add_measurement_to_point(
                        point, rssi, band, dl_speed, ul_speed)

                    self.redraw_all_points()
                    self.highlight_selected_point()
                    self.update_point_info()
                    self.count_label.config(
                        text=f"Puntos totales: {len(self.generator.measurement_points)}")

                elif msg_type == 'error':
                    messagebox.showerror("Error de Medición", message[1])

                elif msg_type == 'finished':
                    self.measure_button.config(state=tk.NORMAL, text="Medición Simple")
                    self.measure_button_auto.config(state=tk.NORMAL, text="Medición x10 (2seg)")

        finally:
            self.root.after(100, self.process_queue)

    def update_point_info(self):
        if not self.selected_point:
            self.point_label.config(text="Punto: Ninguno seleccionado")
            self.point_info_label.config(text="")
            return

        point = self.selected_point
        self.point_label.config(text=f"Punto ID: {point.id}")

        info_text = ""

        count_24 = point.get_measurement_count('2.4')
        if count_24 > 0:
            avg_rssi = point.get_average_rssi('2.4')
            avg_dl = point.get_average_speed('2.4', 'dl')
            avg_ul = point.get_average_speed('2.4', 'ul')

            info_text += f"Banda 2.4 GHz ({count_24} mediciones):\n"
            info_text += f"   RSSI: {avg_rssi} dBm\n"
            if avg_dl is not None:
                info_text += f"   Descarga: {avg_dl} Mbps\n"
            if avg_ul is not None:
                info_text += f"   Subida: {avg_ul} Mbps\n"

        count_5 = point.get_measurement_count('5')
        if count_5 > 0:
            avg_rssi = point.get_average_rssi('5')
            avg_dl = point.get_average_speed('5', 'dl')
            avg_ul = point.get_average_speed('5', 'ul')

            info_text += f"Banda 5 GHz ({count_5} mediciones):\n"
            info_text += f"   RSSI: {avg_rssi} dBm\n"
            if avg_dl is not None:
                info_text += f"   Descarga: {avg_dl} Mbps\n"
            if avg_ul is not None:
                info_text += f"   Subida: {avg_ul} Mbps\n"

        if not info_text:
            info_text = "No hay mediciones para este punto"

        self.point_info_label.config(text=info_text.strip())

    def redraw_all_points(self):
        self.canvas.delete("point")

        for point in self.generator.measurement_points.values():
            has_24 = point.get_measurement_count('2.4') > 0
            has_5 = point.get_measurement_count('5') > 0

            if has_24 and has_5:
                color = '#8e44ad'
                border_color = '#9b59b6'
            elif has_24:
                color = '#3498db'
                border_color = '#5dade2'
            elif has_5:
                color = '#e74c3c'
                border_color = '#ec7063'
            else:
                color = '#95a5a6'
                border_color = '#bdc3c7'

            self.canvas.create_oval(
                point.x - 8, point.y - 8,
                point.x + 8, point.y + 8,
                fill=color,
                outline=border_color,
                width=2,
                tags="point"
            )

            self.canvas.create_text(
                point.x, point.y,
                text=str(point.id),
                fill='white',
                font=('Segoe UI', 8, 'bold'),
                tags="point"
            )

    def highlight_selected_point(self):
        if self.selected_point:
            x, y = self.selected_point.x, self.selected_point.y
            self.canvas.create_oval(
                x - 12, y - 12,
                x + 12, y + 12,
                outline='#f1c40f',
                width=3,
                tags="point"
            )
            self.canvas.create_oval(
                x - 15, y - 15,
                x + 15, y + 15,
                outline='#f39c12',
                width=1,
                tags="point"
            )

    def generate_map(self):
        band = self.band_var.get()

        valid_points = [p for p in self.generator.measurement_points.values()
                        if p.get_average_rssi(band) is not None]

        if len(valid_points) < 4:
            messagebox.showwarning(
                "Datos Insuficientes",
                f"Se necesitan al menos 4 puntos con mediciones para la banda {band} GHz.\n"
                f"Actualmente tienes {len(valid_points)} puntos válidos."
            )
            return

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
                messagebox.showinfo("Éxito",
                    f"Mapa de calor generado y guardado:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error al Generar Mapa",
                    f"No se pudo generar el mapa:\n{str(e)}")

    def save_data(self):
        if not self.generator.measurement_points:
            messagebox.showwarning("Sin Datos", "No hay puntos de medición para guardar")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Guardar Datos de Medición"
        )

        if file_path:
            try:
                self.generator.save_data(file_path)
                messagebox.showinfo("Éxito",
                    f"Datos guardados:\n{file_path}\n\n"
                    f"Puntos guardados: {len(self.generator.measurement_points)}")
            except Exception as e:
                messagebox.showerror("Error al Guardar",
                    f"No se pudieron guardar los datos:\n{str(e)}")

    def load_data(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")],
            title="Cargar Datos de Medición"
        )

        if file_path:
            try:
                self.generator.load_data(file_path)

                self.redraw_all_points()
                self.count_label.config(
                    text=f"Puntos totales: {len(self.generator.measurement_points)}")
                self.ssid_label.config(text=f"SSID: {self.generator.current_ssid}")

                self.select_point(None)
                self.update_point_info()

                messagebox.showinfo("Éxito",
                    f"Datos cargados:\n{file_path}\n\n"
                    f"Puntos: {len(self.generator.measurement_points)}\n"
                    f"SSID: {self.generator.current_ssid}")

            except Exception as e:
                messagebox.showerror("Error al Cargar",
                    f"No se pudo cargar el archivo:\n{str(e)}")

    def clear_all(self):
        if not self.generator.measurement_points:
            messagebox.showinfo("Sin Datos", "No hay puntos para limpiar")
            return

        result = messagebox.askyesno(
            "Confirmar Limpieza",
            f"¿Eliminar todos los {len(self.generator.measurement_points)} puntos?\n\n"
            "Esta acción no se puede deshacer."
        )

        if result:
            self.generator.measurement_points.clear()
            self.generator.next_point_id = 1
            self.generator.current_ssid = None

            self.select_point(None)
            self.redraw_all_points()
            self.count_label.config(text="Puntos totales: 0")
            self.ssid_label.config(text="SSID: (desconocido)")

            messagebox.showinfo("Limpieza Completa",
                                "Todos los puntos han sido eliminados")

    def run(self):
        print("\n" + "="*70)
        print("WiFi Heatmap Generator Pro v8 - Con Mapas Combinados")
        print("="*70)
        print(f"Sistema Operativo: {platform.system()} {platform.release()}")
        print(f"Python: {platform.python_version()}")
        print(f"Detección WiFi: Habilitada para {platform.system()}")
        print(f"Paletas de colores: Seaborn (rocket_r, mako_r)")
        print("="*70)
        print("Listo para usar!")
        print("="*70 + "\n")

        def on_closing():
            if messagebox.askokcancel("Salir", "¿Deseas cerrar la aplicación?"):
                self.root.quit()
                self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", on_closing)

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\nCerrando aplicación...")
            self.root.quit()


if __name__ == "__main__":
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        import scipy.interpolate
        from PIL import Image
        import iperf3
        import seaborn as sns
    except ImportError as e:
        print(f"Error: Falta una dependencia: {e}")
        print("\nPara instalar las dependencias:")
        print("   pip install matplotlib numpy scipy pillow iperf3 seaborn")
        sys.exit(1)

    print(f"Iniciando WiFi Heatmap Generator en {platform.system()}")

    try:
        app = WiFiMapperGUI()
        app.run()
    except Exception as e:
        print(f"Error crítico: {e}")
        messagebox.showerror("Error Crítico",
                             f"No se pudo iniciar la aplicación:\n{str(e)}")
        sys.exit(1)
