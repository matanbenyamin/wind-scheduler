# This file recevis a data frame and a route and plots the wind along the route
import pandas as pd


df = pd.read_csv('wind_data.csv')

route = pd.DataFrame(columns = 'day' ,'')