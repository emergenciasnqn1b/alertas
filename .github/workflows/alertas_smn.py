import requests
from bs4 import BeautifulSoup
from shapely.geometry import Point, Polygon
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import smtplib
import os
import folium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

ciudades = {
    "Chos Malal": (-37.377, -70.270),
    "Andacollo": (-37.15, -70.983),
    "Loncopue": (-38.066, -70.616),
    "Las Lajas": (-38.517, -70.375),
    "Alumine": (-39.233, -71.417),
    "Junin de los Andes": (-39.950, -71.083),
    "San Martin de los Andes": (-40.157, -71.353),
    "Chapelco": (-40.075, -71.137),
    "Bariloche": (-41.133, -71.310),
}

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_PASS")

feed_url = "https://ssl.smn.gob.ar/CAP/AR.php"
feed_resp = requests.get(feed_url)
feed = BeautifulSoup(feed_resp.content, "xml")

alert_links = []
descripciones_feed = {}

for item in feed.find_all("item"):
    link_tag = item.find("link")
    desc_tag = item.find("description")
    if link_tag and desc_tag:
        link = link_tag.text.strip()
        descripcion = desc_tag.text.strip()
        alert_links.append(link)
        descripciones_feed[link] = descripcion

for xml_url in alert_links:
    print(f"Procesando: {xml_url}")
    xml = requests.get(xml_url)
    xml_soup = BeautifulSoup(xml.content, "xml")

    event = xml_soup.find("event")
    evento = event.text if event else "Alerta"

    mapa = folium.Map(location=[-40, -70], zoom_start=5, tiles="CartoDB positron")
    poligono_afecta_ciudad = False
    ciudad_afectada = None

    for area in xml_soup.find_all("area"):
        polygon_tag = area.find("polygon")
        if polygon_tag and polygon_tag.text.strip():
            try:
                coords = []
                for pair in polygon_tag.text.strip().split():
                    lat, lon = map(float, pair.split(','))
                    coords.append((lat, lon))

                if len(coords) >= 3:
                    poligono = Polygon([(lon, lat) for lat, lon in coords])
                    folium.Polygon(
                        locations=coords,
                        color="red",
                        fill=True,
                        fill_opacity=0.4,
                        tooltip=evento
                    ).add_to(mapa)

                    for ciudad, (lat, lon) in ciudades.items():
                        punto = Point(lon, lat)
                        if poligono.contains(punto):
                            ciudad_afectada = ciudad
                            poligono_afecta_ciudad = True
            except Exception as e:
                print(f"Error procesando poligono: {e}")

    if poligono_afecta_ciudad:
        for nombre, (lat, lon) in ciudades.items():
            folium.Marker(
                location=(lat, lon),
                popup=nombre,
                tooltip=nombre,
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(mapa)

        mapa.save("mapa_alerta.html")

        # Captura imagen con Selenium
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1200,800")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("file://" + os.path.abspath("mapa_alerta.html"))
        time.sleep(3)
        driver.save_screenshot("mapa_alerta.png")
        driver.quit()

        descripcion_extra = descripciones_feed.get(xml_url, "(Sin descripcion adicional)")

        mensaje = MIMEMultipart("related")
        mensaje["Subject"] = f"🚨 {evento} en {ciudad_afectada}"
        mensaje["From"] = GMAIL_USER
        mensaje["To"] = GMAIL_USER

        cuerpo_html = f'''
            <html>
              <body>
                <p><strong>Se detecto una alerta meteorologica que afecta a {ciudad_afectada}.</strong></p>
                <p><strong>Descripcion:</strong><br>{descripcion_extra}</p>
                <img src="cid:mapa_alerta">
              </body>
            </html>
        '''

        parte_html = MIMEText(cuerpo_html, "html")
        mensaje.attach(parte_html)

        with open("mapa_alerta.png", "rb") as f:
            img = MIMEImage(f.read())
            img.add_header("Content-ID", "<mapa_alerta>")
            mensaje.attach(img)

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(GMAIL_USER, GMAIL_PASS)
                smtp.send_message(mensaje)
            print(f"✅ Correo enviado por alerta en {ciudad_afectada}")
        except Exception as e:
            print(f"❌ Error al enviar correo: {e}")