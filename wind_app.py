import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.action_chains import ActionChains
import re
import pandas as pd
from webdriver_manager.firefox import GeckoDriverManager
import folium
from streamlit_folium import st_folium
import pydeck as pdk
import numpy as np


# Function to get wind data
def get_wind_data(lat, lon, date, hour, progress_bar, status_text):
    options = FirefoxOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    service = FirefoxService(executable_path=GeckoDriverManager().install())

    driver = webdriver.Firefox(service=service, options=options)

    try:
        latlong = f"{lat}/{lon}"
        url = f'https://www.windfinder.com/#11/{latlong}/{date}T{hour}Z'
        driver.get(url)
        # Get the dimensions of the webpage
        window_size = driver.get_window_size()
        width = window_size['width']
        height = window_size['height']
        # Calculate the center coordinates
        center_x = width // 2
        center_y = height // 3
        # Perform the mouse click in the center of the webpage
        actions = ActionChains(driver)
        actions.move_by_offset(center_x, center_y).click().perform()
        time.sleep(3)
        # Find all iframes on the page
        iframes = driver.find_elements(By.TAG_NAME, 'iframe')
        found = False
        # Iterate through each iframe and try to switch to it
        for index, iframe in enumerate(iframes):
            try:
                status_text.text(f"Attempting to switch to iframe {index + 1}")
                driver.switch_to.frame(iframe)
                status_text.text(f"Switched to iframe {index + 1}")
                driver.switch_to.default_content()  # Switch back to the main content after testing
                # look for the element
                elements = driver.find_elements(By.CLASS_NAME, '_3KkQP69rYwNnTAe8GyxgmA')

                speed = None
                direction = None
                direction_deg = None
                for element in elements:
                    status_text.text(f"Processing element: {element.text}")
                    found = True
                    text = element.text
                    text = re.sub(r'[^\x00-\x7F]+', '', text)

                    # structure the data - if (str) its a direction, if kts in text its strnegth
                    if 'kts' in element.text:
                        # format utf-8
                        speed = int(text.split('kts')[0])
                    if '°' in element.text:
                        direction_deg = int(element.text.split('°')[0])
                        direction = text.split('(')[1][:-1]
                if found:
                    break
            except Exception as e:
                status_text.text(f"Could not switch to iframe {index + 1}: {e}")
    finally:
        driver.quit()

    return speed, direction, direction_deg


# Streamlit app
st.title("Wind Data Finder v2")

# Initialize session state for selected positions if not already done
if 'selected_positions' not in st.session_state:
    st.session_state.selected_positions = []

# Initialize session state for dates and names if not already done
if 'dates' not in st.session_state:
    st.session_state.dates = [[] for _ in range(len(st.session_state.selected_positions))]
if 'names' not in st.session_state:
    st.session_state.names = [""] * len(st.session_state.selected_positions)

# Map for selecting positions
st.header("Select Positions on Map")
initial_coords = [38.5, 20.7]

map_ = folium.Map(location=initial_coords, zoom_start=8)
map_.add_child(folium.LatLngPopup())

map_clicks = st_folium(map_, width=700, height=500)

if map_clicks['last_clicked']:
    lat, lon = map_clicks['last_clicked']['lat'], map_clicks['last_clicked']['lng']
    if (lat, lon) not in st.session_state.selected_positions:
        st.session_state.selected_positions.append((lat, lon))
        st.session_state.dates.append([])
        st.session_state.names.append("")

selected_positions = st.session_state.selected_positions

if selected_positions:
    for i, pos in enumerate(selected_positions):
        st.write(f"Position {i + 1}: {pos}")

        # User input for position name
        name = st.text_input(f'Name for Position {i + 1}', value=st.session_state.names[i], key=f'name_{i}')
        st.session_state.names[i] = name

        # User input for dates for each position
        dates = st.date_input(f'Select Dates for Position {i + 1}', value=st.session_state.dates[i], key=f'dates_{i}')
        if isinstance(dates, tuple):
            dates = list(dates)
        else:
            dates = [dates]

        st.session_state.dates[i] = dates

        # Button to remove the position
        if st.button(f'Remove Position {i + 1}', key=f'remove_{i}'):
            del st.session_state.selected_positions[i]
            del st.session_state.dates[i]
            del st.session_state.names[i]
            st.experimental_rerun()

# Common hours selection for all positions
st.header("Select Hours for All Positions")
available_hours = ['09:00', '12:00', '15:00', '18:00', '14:00', '17:00']
default_hours = ['09:00', '14:00', '17:00']
hours = st.multiselect('Select Hours', available_hours, default=default_hours)

# Button to start scraping
if st.button('Get Wind Data'):
    progress_bar = st.progress(0)
    progress = 0
    total_tasks = sum(len(dates) * len(hours) for dates in st.session_state.dates)
    status_text = st.empty()

    output = pd.DataFrame(columns=['name', 'lat', 'lon', 'date', 'hour', 'speed', 'direction', 'direction_deg'])

    for i, pos in enumerate(selected_positions):
        lat, lon = pos
        name = st.session_state.names[i]
        dates = st.session_state.dates[i]
        for date in dates:
            for hour in hours:
                status_text.text(f'Getting data for {name} ({lat}, {lon}) on {date} at {hour}')
                data = get_wind_data(lat, lon, date, hour, progress_bar, status_text)
                output = pd.concat([output, pd.DataFrame(
                    {'name': name, 'lat': lat, 'lon': lon, 'date': date, 'hour': hour, 'speed': data[0],
                     'direction': data[1],
                     'direction_deg': data[2]}, index=[0])])
                progress += 1
                progress_bar.progress(progress / total_tasks)

    # Display the results
    st.write(output)

    # Create map layers for wind speed and direction
    layers = []
    for _, row in output.iterrows():
        arrow_length = 0.01  # Length of the arrow
        direction_rad = row['direction_deg'] * (3.14159265 / 180)  # Convert to radians
        layers.append(pdk.Layer(
            "PathLayer",
            data=pd.DataFrame([{
                'path': [
                    [row['lon'], row['lat']],
                    [row['lon'] + arrow_length * np.cos(direction_rad),
                     row['lat'] + arrow_length * np.sin(direction_rad)]
                ],
                'wind_speed': row['speed']
            }]),
            get_path='path',
            get_width=2,
            get_color=[0, 0, 255],
            pickable=True,
        ))
        layers.append(pdk.Layer(
            "TextLayer",
            data=pd.DataFrame([{
                'coordinates': [row['lon'], row['lat']],
                'text': f"{row['name']}: {row['speed']} kts"
            }]),
            get_position="coordinates",
            get_text="text",
            get_size=16,
            get_color=[0, 0, 0],
            get_alignment_baseline="'bottom'",
        ))

    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v10",
        initial_view_state=pdk.ViewState(
            latitude=initial_coords[0],
            longitude=initial_coords[1],
            zoom=8,
            pitch=50,
        ),
        layers=layers
    ))
