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

# Function to get wind data (place your get_wind_data function here)
def get_wind_data(driver, date, hour, latlong):
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
            print(f"Attempting to switch to iframe {index + 1}")
            driver.switch_to.frame(iframe)
            print(f"Switched to iframe {index + 1}")
            driver.switch_to.default_content()  # Switch back to the main content after testing
            # look for the element
            elements = driver.find_elements(By.CLASS_NAME, '_3KkQP69rYwNnTAe8GyxgmA')

            speed = None
            direction = None
            direction_deg = None
            for element in elements:
                print(element.text)
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
            print(f"Could not switch to iframe {index + 1}: {e}")

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

# User input for dates
dates = st.date_input('Select Dates', [])
if isinstance(dates, tuple):
    dates = list(dates)
else:
    dates = [dates]

# Fixed hours
hours = ['09:00', '14:00', '17:00']

# Tabs for main content and adding new positions
tab1, tab2 = st.tabs(["Wind Data", "Add New Position"])

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

with tab1:
    # Display current positions
    st.header("Current Positions")
    for pos_name, coords in st.session_state.positions.items():
        st.write(f"{pos_name}: {coords}")

    # Button to start scraping
    if st.button('Get Wind Data'):
        webdriver_path = '/opt/homebrew/bin/chromedriver'
        options = Options()
        options.add_argument('--disable-infobars')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        service = Service(webdriver_path)

        # install the chromedriver
        driver = webdriver.Chrome(options=options)

        output = pd.DataFrame(columns=['pos', 'date', 'hour', 'speed', 'direction', 'direction_deg'])
        for date in dates:
            for hour in hours:
                for pos, coords in st.session_state.positions.items():
                    driver = webdriver.Chrome(options=options)
                    st.write(f'Getting data for {pos} {date} at {hour}')
                    latlong = str(coords[0]) + '/' + str(coords[1])
                    data = get_wind_data(driver, date, hour, latlong)
                    output = pd.concat([output, pd.DataFrame(
                        {'pos': pos, 'date': date, 'hour': hour, 'speed': data[0], 'direction': data[1],
                         'direction_deg': data[2]}, index=[0])])
                    output.to_csv('wind_data.csv', index=False)
                    driver.quit()

        # Display the results
        st.write(output)
