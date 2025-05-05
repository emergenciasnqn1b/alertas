import os
import time
import requests
import smtplib
import folium
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from shapely.geometry import Point, Polygon

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Coordenadas de ciudades de interés
ciudades = {
    "Chos Malal": (-37.377, -70.270),
    "Andacollo": (-37.15, -70.983),
    "Loncopué": (-38.066, -70.616),
    "Las Lajas": (-38.517, -70.375),
    "Aluminé": (-39.233, -71.417),
    "Junín de los Andes": (-39.950, -71.083),
    "San Martín de los Andes": (-40.157, -71.353),
    "Chapelco": (-40.075, -71.137),
    "Bariloche": (-41.133, -71.310),
}

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")

def generar_mapa(polygon_coords, ciudad_afectada):
    m = folium.Map(location=[-40, -70], zoom_start=6)
    folium.Polygon(polygon_coords, color='red', fill=True, fill_opacity=0.4).add_to(m)
    for nombre, (lat, lon) in ciudades.items():
        folium.Marker([lat, lon], tooltip=nombre, icon=folium.Icon(color='blue')).add_to(m)
    folium.Marker(ciudades[ciudad_afectada], tooltip=ciudad_afectada,
                  icon=folium.Icon(color='red', icon='info-sign')).add_to(m)
    m.save("alerta_mapa.html")

def capturar_mapa():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_window_size(600, 600)
    driver.get("file://" + os.path.abspath("alerta_mapa.html"))
    time.sleep(3)
    driver.save_screenshot("alerta_mapa.png")
    driver.quit()

def enviar_mail(ciudad, descripcion):
    mensaje = MIMEMultipart("related")
    mensaje["Subject"] = f"🚨 Alerta Meteorológica en {ciudad}"
    mensaje["From"] = GMAIL_USER
    mensaje["To"] = GMAIL_USER

    cuerpo_html = f"""
    <html>
        <body>
            <p><strong>Se detectó una alerta que afecta a {ciudad}.</strong></p>
            <p>{descripcion}</p>
            <a href="https://www.smn.gob.ar/alertas" target="_blank">
                <img src="cid:mapa_alerta" style="max-width: 100%; border: 1px solid #ccc;">
            </a>
        </body>
    </html>
    """

    parte_html = MIMEText(cuerpo_html, "html")
    mensaje.attach(parte_html)

    with open("alerta_mapa.png", "rb") as f:
        img = MIMEImage(f.read())
        img.add_header("Content-ID", "<mapa_alerta>")
        mensaje.attach(img)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.send_message(mensaje)

def main():
    feed_url = "https://ssl.smn.gob.ar/CAP/AR.php"
    feed = BeautifulSoup(requests.get(feed_url).content, "xml")
    for item in feed.find_all("item"):
        link = item.find("link").text.strip()
        desc = item.find("description").text.strip()
        xml = BeautifulSoup(requests.get(link).content, "xml")

        for area in xml.find_all("area"):
            polygon = area.find("polygon")
            if not polygon: continue

            coords = [(float(lat), float(lon)) for lat, lon in (p.split(',') for p in polygon.text.strip().split())]
            poly = Polygon([(lon, lat) for lat, lon in coords])  # shapely: (lon, lat)

            for ciudad, (lat, lon) in ciudades.items():
                if poly.contains(Point(lon, lat)):
                    generar_mapa(coords, ciudad)
                    capturar_mapa()
                    enviar_mail(ciudad, desc)
                    print(f"✅ Alerta enviada para {ciudad}")
                    return

if __name__ == "__main__":
    main()
