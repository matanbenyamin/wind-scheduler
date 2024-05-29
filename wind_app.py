import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
import re
import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import pydeck as pdk

# Function to get wind data (place your get_wind_data function here)
def get_wind_data(driver, date, hour, latlong, progress_bar, status_text):
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

    return speed, direction, direction_deg


# Streamlit app
st.title("Wind Data Finder")

# Initialize session state for positions if not already done
if 'positions' not in st.session_state:
    st.session_state.positions = {
        'lefkada_canal': [38.7825, 20.7322],
        'meganisi': [38.623, 20.7707],
        'atokos': [38.4729, 20.8170],
        'kioni': [38.4473, 20.6950],
        'filiatru': [38.3744, 20.7442],
        'to_sivota': [38.5251, 20.5534],
        'vathi': [38.3711, 20.7127]
    }

if 'routes' not in st.session_state:
    st.session_state.routes = []

# User input for dates
dates = st.date_input('Select Dates', [])
if isinstance(dates, tuple):
    dates = list(dates)
else:
    dates = [dates]

# User input for hours
available_hours = ['09:00', '12:00', '15:00', '18:00', '14:00', '17:00']
default_hours = ['09:00', '14:00', '17:00']
hours = st.multiselect('Select Hours', available_hours, default=default_hours)

# Tabs for main content, adding new positions, and managing routes
tab1, tab2, tab3 = st.tabs(["Wind Data", "Manage Positions", "Manage Routes"])

with tab2:
    st.header("Add New Position")
    new_pos_name = st.text_input("Position Name")
    new_pos_lat = st.text_input("Latitude")
    new_pos_long = st.text_input("Longitude")

    if st.button("Add Position"):
        try:
            new_pos_lat = float(new_pos_lat)
            new_pos_long = float(new_pos_long)
            st.session_state.positions[new_pos_name] = [new_pos_lat, new_pos_long]
            st.success(f"Added position {new_pos_name} with coordinates [{new_pos_lat}, {new_pos_long}]")
        except ValueError:
            st.error("Please enter valid latitude and longitude values.")

    st.header("Remove Position")
    pos_to_remove = st.selectbox("Select Position to Remove", list(st.session_state.positions.keys()))
    if st.button("Remove Position"):
        if pos_to_remove in st.session_state.positions:
            del st.session_state.positions[pos_to_remove]
            st.success(f"Removed position {pos_to_remove}")

with tab3:
    st.header("Manage Routes")
    for date in dates:
        st.subheader(f"Route for {date}")
        from_pos = st.selectbox(f"From (date: {date})", list(st.session_state.positions.keys()), key=f"from_{date}")
        to_pos = st.selectbox(f"To (date: {date})", list(st.session_state.positions.keys()), key=f"to_{date}")
        if st.button(f"Save Route for {date}"):
            st.session_state.routes.append({
                'date': date,
                'from': from_pos,
                'to': to_pos
            })
            st.success(f"Route for {date} saved from {from_pos} to {to_pos}")

    # Display saved routes
    if st.session_state.routes:
        st.subheader("Saved Routes")
        for route in st.session_state.routes:
            st.write(f"{route['date']}: From {route['from']} to {route['to']}")

with tab1:
    # Display current positions
    st.header("Current Positions")
    for pos_name, coords in st.session_state.positions.items():
        st.write(f"{pos_name}: {coords}")

    # Display map with positions and routes
    st.header("Map of Positions and Routes")
    map_data = pd.DataFrame([{'lat': coords[0], 'lon': coords[1]} for coords in st.session_state.positions.values()])
    st.map(map_data)

    if st.session_state.routes:
        route_data = []
        for route in st.session_state.routes:
            from_coords = st.session_state.positions[route['from']]
            to_coords = st.session_state.positions[route['to']]
            route_data.append({
                'date': route['date'],
                'from_lat': from_coords[0],
                'from_lon': from_coords[1],
                'to_lat': to_coords[0],
                'to_lon': to_coords[1]
            })
        route_df = pd.DataFrame(route_data)
        st.write(route_df)

        # Create map layers for routes with wind speed and direction
        layers = []
        for _, row in route_df.iterrows():
            layers.append(pdk.Layer(
                "LineLayer",
                data=pd.DataFrame([{
                    'source_position': [row['from_lon'], row['from_lat']],
                    'target_position': [row['to_lon'], row['to_lat']],
                    'wind_speed': row.get('wind_speed', 0),
                    'wind_direction_deg': row.get('wind_direction_deg', 0)
                }]),
                get_source_position="source_position",
                get_target_position="target_position",
                get_color=[255, 0, 0, 160],
                get_width=5
            ))

        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v10",
            initial_view_state=pdk.ViewState(
                latitude=38.5,
                longitude=20.7,
                zoom=8,
                pitch=50,
            ),
            layers=layers
        ))

    # Button to start scraping
    if st.button('Get Wind Data'):
        webdriver_path = ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install()
        options = Options()
        options.add_argument('--disable-infobars')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        service = Service(webdriver_path)

        total_tasks = len(dates) * len(hours) * len(st.session_state.positions)
        progress_bar = st.progress(0)
        progress = 0
        status_text = st.empty()

        output = pd.DataFrame(columns=['pos', 'date', 'hour', 'speed', 'direction', 'direction_deg'])
        for date in dates:
            for hour in hours:
                for pos, coords in st.session_state.positions.items():
                    driver = webdriver.Chrome(service=service, options=options)
                    status_text.text(f'Getting data for {pos} {date} at {hour}')
                    latlong = str(coords[0]) + '/' + str(coords[1])
                    data = get_wind_data(driver, date, hour, latlong, progress_bar, status_text)
                    output = pd.concat([output, pd.DataFrame(
                        {'pos': pos, 'date': date, 'hour': hour, 'speed': data[0], 'direction': data[1],
                         'direction_deg': data[2]}, index=[0])])
                    progress += 1
                    progress_bar.progress(progress / total_tasks)
                    driver.quit()

        # Display the results
        st.write(output)

        # Update route data with wind information
        for route in st.session_state.routes:
            from_coords = st.session_state.positions[route['from']]
            latlong_from = f"{from_coords[0]}/{from_coords[1]}"
            for hour in hours:
                wind_speed, wind_direction, wind_direction_deg = get_wind_data(driver, route['date'], hour, latlong_from, progress_bar, status_text)
                route['wind_speed'] = wind_speed
                route['wind_direction'] = wind_direction
                route['wind_direction_deg'] = wind_direction_deg

        route_df = pd.DataFrame(route_data)
        st.write(route_df)
