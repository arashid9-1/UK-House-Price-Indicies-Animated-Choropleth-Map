import numpy as np
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import geopandas as gpd
import os
import folium
import plotly.express as px
import seaborn as sns



# Read in indices and clean dataframe
interp_index = pd.read_table(r"C:\Users\Dell\Documents\ali_gis\postcode_districts_130923.csv", sep = ",")

uniq_dates = [[year+'-'+month for month in np.array(range(1,13)).astype(str)]for year in np.array(range(1995,2024)).astype(str)]
uniq_dates = np.array(uniq_dates).flatten()
interp_index.columns = map(str.upper, interp_index.columns)
interp_index['DATEID01'] = uniq_dates
interp_index = interp_index.rename(columns={'DATEID01' : 'time'})
interp_index = interp_index.set_index('time')
interp_index_dict = {dist: interp_index[dist].to_dict() for dist in interp_index.columns}


''' Extract geometry data from geojson files '''
#download from https://longair.net/blog/2021/08/23/open-data-gb-postcode-unit-boundaries/


root_dir = r''

gdf_list = []

for subdir, dirs, files in os.walk(root_dir):
    for file in files:
        # Check if the file is a GeoJSON file just incase
        if file.endswith('.geojson'):
            file_path = os.path.join(subdir, file)
            gdf = gpd.read_file(file_path)
            gdf_list.append(gdf)

# Concatenate all geodataframes into one gdf
full_gdf = gpd.GeoDataFrame(pd.concat(gdf_list, ignore_index=True))


''' Save sector boundary data to easily load next time '''

full_gdf.to_file('/Users/ali/Desktop/Fathom Project/GIS_extension/sectors_boundaries.shp')
#full_gdf = gpd.read_file("sectors_boundaries.shp")

''' The geometry data is simplifed to make animation rendoring less intensive '''

full_gdf["geometry"] = (
    full_gdf.to_crs(full_gdf.estimate_utm_crs()).simplify(1000).to_crs(full_gdf.crs)
)
full_gdf.dropna(axis=0, subset="geometry", how="any", inplace=True)
full_gdf.set_index("sector")
full_gdf = full_gdf.to_crs(epsg=4326)

''' Melt the indices df to convert to long format '''
''' Merge indices df with gdf to add geometry dimension '''
''' Subset data to take only select dates for memeory reasons '''

interp_index.reset_index(inplace=True)
interp_index =  pd.melt(interp_index, id_vars=['time'], var_name='sector', value_name='index')

merged_gdf = full_gdf.merge(interp_index, on='sector')
merged_gdf['time'] = pd.to_datetime(merged_gdf['time'] + '-1', format='%Y-%m-%d')
merged_gdf = merged_gdf[merged_gdf['index'].notna()]
merged_gdf.sort_values('time', inplace=True)

dates = [f"{year}-01-01" for year in range(2005, 2024, 3)]
dates = pd.to_datetime(dates)

test_gdf = merged_gdf[merged_gdf['time'].isin(dates)].copy()

''' Chloropleth map animation '''



test_gdf['year'] = test_gdf['time'].dt.year

test_gdf['decile'] = test_gdf.groupby('time')['index'].transform(
    lambda x: pd.qcut(x, q=10, labels=False, duplicates='drop'))

# Update your mapbox access token setup if necessary
px.set_mapbox_access_token('MY ACCESS TOEKN')


fig = px.choropleth_mapbox(
    test_gdf,
    geojson=test_gdf.geometry,
    locations=test_gdf.index,
    color="decile",
    # color_continuous_scale="Aggrnyl",
    color_continuous_scale="Viridis",
    mapbox_style='mapbox://styles/mapbox/navigation-day-v1',
    zoom=5,
    center={"lat": 53.0, "lon": -2.5}, 
    opacity=0.7,
    hover_data={'sector': True, 'index': True, 'decile': True},
    animation_frame=test_gdf['year'].astype(str),
    range_color=[0, 9], )

# Colouring based on index deciles distribution between periods
fig.update_coloraxes(colorbar=dict(
    title="Decile",
    tickvals=list(range(10)),
    ticktext=[f'Decile {i+1}' for i in range(10)]))

# Set bounds for the map to focus on England and Wales
bounds = {
    "lataxis_range": [49.5, 55.9],
    "lonaxis_range": [-6.5, 2.1],}

fig.update_geos(
    lataxis_range=bounds["lataxis_range"],
    lonaxis_range=bounds["lonaxis_range"],
    visible=False
)

fig.update_layout(
    sliders=[{
        'pad': {'t': 10}, 
        'len': 0.8,  
        'x': 0.1,  
        'y': 0,  
        'currentvalue': {'visible': True, 'prefix': 'Time: '},
        'transition': {'duration': 300},
        'steps': [] }])

fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
fig.show()

#Save
fig.write_html("sectors_vis7.html")



''' Static px chloropleth map'''

indices = interp_index.copy()
indices = indices.dropna(subset=['index'])
indices = indices[indices['time'].isin(['2023-1', '2008-1'])]
indices['decile'] = indices.groupby('time')['index'].transform(
    lambda x: pd.qcut(x, q=10, labels=False, duplicates='drop'))


indices.set_index('sector', inplace=True)

p_indices = indices.pivot(columns='time', values='decile')


p_indices['decile_change'] = p_indices['2023-1'] - p_indices['2008-1']

p_indices['abs_change'] = p_indices['decile_change'].abs()
p_indices = p_indices.sort_values(by='abs_change', ascending=False)

p_indices = p_indices.replace(0, np.nan).dropna()
p_indices.reset_index(inplace=True)

# Merge
merged_df = full_gdf.merge(p_indices, on='sector')
geojson = merged_df.geometry.__geo_interface__

px.set_mapbox_access_token('MY ACCESS TOKEN')
fig = px.choropleth_mapbox(merged_df,
                           geojson=geojson,
                           locations=merged_df.index,
                           color="decile_change", 
                           color_continuous_scale=px.colors.diverging.Picnic, 
                           mapbox_style='mapbox://styles/mapbox/navigation-night-v1',
                           zoom=5, center={"lat": 53.0, "lon": -2.5},
                           hover_data={'decile_change':True, 'sector':True, 'index':False},
                           opacity=0.7,
                           labels={'decile_change': 'Decile Change'})

fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
fig.show()

# Save

fig.write_html("dc_vis3.html")

