#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 25 00:22:28 2024

@author: rahulsingh
"""

import streamlit as st
import geopandas as gpd
import rasterio
from shapely import wkt
from rasterio.mask import mask
import plotly.io as pio 
from rasterio.plot import show
from rasterio.mask import geometry_mask
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os, io
from PIL import Image
import base64
import altair as alt
import matplotlib.pyplot as plt
import leafmap.foliumap as leafmap
from streamlit_folium import st_folium
from pathlib import Path
from matplotlib.colors import LinearSegmentedColormap
import tempfile
import zipfile
from io import BytesIO
from rasterio.io import MemoryFile
from scipy.interpolate import griddata
import folium
from shapely.geometry import box, Point
from sklearn.cluster import KMeans
from mgwr.gwr import GWR
from mgwr.sel_bw import Sel_BW
from rasterio.plot import show
import matplotlib.pyplot as plt


# Configure page
#st.set_page_config(page_title="TAPS Agricultural Data Dashboard", layout="centered")
# Page configuration
st.set_page_config(
    page_title="TAPS Agricultural Data Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://docs.streamlit.io",
        "Report a Bug": "https://github.com/streamlit/streamlit/issues",
        "About": "This app processes and visualizes spatial and tabular data."
    }
)
# Enable Altair theme
alt.themes.enable("default")
 # Sidebar with navigation and logo
st.sidebar.image("./taps_logo.png", width= 180)  # Add logo in the sidebar
st.sidebar.title("Navigation")
main_dataset_folder = "./Datasets"
output_folder_name = "Output"
page = st.sidebar.selectbox("Choose a page", ["Home", "Data Visualization", "Data Management", "Data Analysis", "Data Interpretation"])
interpolation_method = 'idw'

def strip_time(date_str):
            try:
                return pd.to_datetime(date_str).strftime('%Y-%m-%d')
            except Exception as e:
                print(f"Error parsing date: {date_str}. Exception: {str(e)}")
                return date_str
            
def is_date(string):
    try:
        pd.to_datetime(string)
        return True
    except ValueError:
        return False

def set_axis_function(data_to_plot):
    position = []    
    if data_to_plot == "NDVI":
        return "NDVI"
    elif data_to_plot == "MCARI2":
        return "MCARI2"
    elif data_to_plot == "Irrigation":
        return "Irrigation"
    else:
        return "Fertilizer"
    
        
def set_title_function(data_to_plot):
    if data_to_plot == "NDVI":
        return "NDVI"
    elif data_to_plot == "MCARI2":
        return "MCARI2"
    elif data_to_plot == "Irrigation":
        return "Irrigation (inches)"
    else:
        return "Fertilizer (lbs/acre)"

def set_plot_dataframe(data_to_plot):
    if data_to_plot == "NDVI":
        data = ndvi_dataframes.groupby('TRT_ID')[f'mean_NDVI_{st.session_state["selected_date_str"]}'].mean()
        return data
    elif data_to_plot == "MCARI2":
        data = ndvi_dataframes.groupby('TRT_ID')[f'mean_MCARI2_{st.session_state["selected_date_str"]}'].mean()
        return data
    elif data_to_plot == "Irrigation":
        data = plot_sums_df[f'{data_to_plot}']
        return data
    else:
        data = plot_sums_df[f'{data_to_plot}']
        return data
    
def create_dataframes():

    Ma_path = Path(__file__).parent / "./Datasets/Management/2024_TAPS_management.xlsx"
    MA_excel_file = pd.ExcelFile(Ma_path)

    data_frames = []
    for sheet_name in MA_excel_file.sheet_names:
        if sheet_name == "Planting date" or sheet_name == "Irrigation amounts":
            sheet_data = pd.read_excel(MA_excel_file, sheet_name=sheet_name, index_col=None,  header=[0, 1])
            # sheet_data = sheet_data.drop(sheet_data.columns[0], axis=1)

            if sheet_name == "Irrigation amounts":
                new_columns = []
                for col in sheet_data.columns:
                    if is_date(col[1]):
                        new_columns.append(f"{col[0]}_{strip_time(col[1])}")
                    else:
                        if col[0] != 'Unnamed: 0_level_0':
                            new_columns.append(f"{col[0]}_{col[1]}")
                        else:
                            new_columns.append(col[1])
                        
                sheet_data.columns = new_columns
                duplicate_columns = sheet_data.columns[sheet_data.columns.duplicated()]
                for col in duplicate_columns: 
                    # Find columns with the same name 
                    col_idx = [i for i, x in enumerate(sheet_data.columns) if x == col] 
                    # Compare values 
                    if sheet_data.iloc[:, col_idx[0]].equals(sheet_data.iloc[:, col_idx[1]]): 
                        # If values are the same, drop the second column 
                        sheet_data.drop(sheet_data.columns[col_idx[1]], axis=1, inplace=True) 
                    else: 
                        # If values are different, sum the columns 
                        sheet_data.iloc[:, col_idx[0]] += sheet_data.iloc[:, col_idx[1]] 
                        # Drop the second column 
                        sheet_data.drop(sheet_data.columns[col_idx[1]], axis=1, inplace=True)
                duplicate_columns = sheet_data.columns[sheet_data.columns.duplicated()]        
                print(duplicate_columns)
            else:
                sheet_data.columns = [f"{col[0]}_{col[1]}" for col in sheet_data.columns]
            data_frames.append(sheet_data) 
             
    
        if sheet_name == "Nitroge fertilizer":
            sheet_data = pd.read_excel(MA_excel_file, sheet_name=sheet_name, index_col=None, header=[0, 1, 2])
            
            new_columns = []
            for col in sheet_data.columns:
                if is_date(col[2]):
                    new_columns.append(f"{col[0]}_{col[1]}_{strip_time(col[2])}")
                else:
                    if col[0] != 'Unnamed: 0_level_0':
                        new_columns.append(f"{col[0]}_{col[1]}_{col[2]}")
                    else:
                        new_columns.append(col[2])
        
            sheet_data.columns = new_columns
            data_frames.append(sheet_data)  

    pldate_df = data_frames[0]
    nfert_df = data_frames[1]
    irr_df = data_frames[2]

    # Step 1: Merge pldate_df with nfert_df using Farm ID and ID
    merged_df = pd.merge(pldate_df, nfert_df, left_on="Farm_ID", right_on="ID", how="inner")
    merged_df = merged_df.drop(columns = 'ID')

    #Step 2: Merge the result with irr_df using Farm ID and ID
    merged_df1 = pd.merge(merged_df, irr_df, left_on="Farm_ID", right_on="ID", how="inner")

    # Drop duplicate ID columns if necessary
    merged_df2 = merged_df1.drop(columns=["ID_x", "ID_y"], errors="ignore")  # Keep only the Farm ID column
    
    # Loop through each column and convert data type if it's 'str' or 'object'
    for col in merged_df2.columns:
        if merged_df2[col].dtype == "object" or merged_df2[col].dtype == "str":
            try:
                merged_df2[col] = merged_df2[col].astype("float64")
            except ValueError:
                print(f"Column {col} could not be converted to float64.")
    # Display the merged dataframe
    return merged_df2, pldate_df, nfert_df, irr_df
    
merged_df, plate_df, nfert_df, irr_df = create_dataframes()

# Display Home Page content with logo positioned in the lower right and background image
if page == "Home":
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'> TAPS Agricultural Data Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #000000;'>Turning Data Complexity into Practical Insights for Precision Agriculture</h3>", unsafe_allow_html=True)
    # Banner Image (replace with a local file path or URL if needed)
    colh1,colh2,colh3 = st.columns([0.15,0.70,0.15])
    with colh2:
        st.image("./iot-in-agriculture.jpg", caption="Empowering Decision-Making in Agriculture", use_column_width = True)

    st.markdown(f"<br><h3 style='color:#4CAF50;'>Welcome to the TAPS Agricultural Data Dashboard</h3>", unsafe_allow_html=True)

    # Introduction Section
    st.markdown("""

    In a rapidly advancing agricultural landscape, access to timely, organized, and interpretable data is crucial for optimizing crop management and resource allocation. This dashboard aims to bridge the gap between data complexity and practical insights, providing a user-friendly platform for visualizing, managing, and analyzing both spatial and non-spatial components of the TAPS dataset. The dashboard supports a broad range of agricultural stakeholders, from researchers to producers, by delivering tailored insights that enhance decision-making at every stage of the cropping cycle.

    By integrating spatial data—such as soil properties, field conditions, and vegetation indices—with non-spatial metrics—such as treatment information and crop yields—this dashboard offers a holistic view of field dynamics. The motivation behind this project is to create a tool that is not only technically robust but also accessible, allowing users to interact with complex data layers effortlessly. This approach helps unlock the potential of precision agriculture, guiding resource-efficient practices, boosting productivity, and advancing sustainable agricultural practices through data-driven insights."
    """)
    # Core Features Section
    st.markdown("<h3 style='text-align: center; color: #000000;'>Core Features</h3>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### Data Visualization")
        st.write("Easily explore spatial and non-spatial data, including field conditions, soil properties, and crop performance metrics.")
        
    with col2:
        st.markdown("#### Data Management")
        st.write("Organize and manage datasets efficiently to maintain a comprehensive view of field dynamics throughout the cropping cycle.")
            
    with col3:
        st.markdown("#### Analytical Insights")
        st.write("Leverage data-driven insights to inform every stage of crop management, enhancing resource allocation and productivity.")
        
    # How It Works Section
    st.markdown("### How It Works")
    st.markdown("""
    1. **Upload your data** or connect to available datasets.
    2. **Visualize and manage** spatial and non-spatial data layers.
    3. **Analyze trends** to guide decision-making.
    """)

    # Impact Statement Section
    st.markdown("### Empowering Researchers, Producers, and Stakeholders")
    st.write("With tailored insights at every stage of the cropping cycle, our dashboard is designed to support informed decisions, boost productivity, and promote sustainable practices in agriculture.")

    # Get Started Button
    if st.button("Get Started"):
        st.write("Redirecting to the dashboard...")
        page = "Data Visualization"  # Replace with actual dashboard navigation

    # Footer Section
    st.markdown("---")
    st.markdown("**Contact Information**")
    st.write("For support or questions, please contact us at [farmslab@ksu.edu](mailto:support@tapsdashboard.com).")
    
    "**Team Members:**"
    # Create three columns
    col1, col2, col3 = st.columns(3)

    # Add unique information to each column
    with col1:
        st.markdown("""
        
                    
        Aashvi Dua
        
         Email: aashvidua@ksu.edu
        """)

    with col2:
        st.markdown("""
                    


        Benjamin Vail

         Email: benv86@ksu.edu
        """)

    with col3:
        st.markdown("""
        
       
        Rahul Singh 
                    
        Email: rahul2401@ksu.edu
        """)
        
    st.markdown("**Acknowledgment**")
    st.write("Developed by the Farms Lab Team as part of the TAPS Hackathon at Kansas State University.")

    # Load TAPS Logo in the center
    col1, col2, col3 = st.columns([1, 1, 1])  # Adjust column widths to center the image
    with col2:
        st.image("./taps_logo.png", use_column_width = True)
    # Data input

elif page =="Data Visualization":
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'> TAPS Data Input & Visualization</h1>", unsafe_allow_html=True)
    st.markdown("<h5 style='text-align: center; color: #6c757d;'> Unlocking insights through spatial data visualization and analysis</h3>", unsafe_allow_html=True)


    ######################## Data Visualization and data input ##################
    st.markdown("<h3 style='text-align: center; color: #6c757d;'> Spatial Data Input & Display </h3>", unsafe_allow_html=True)

    ###Setting input and ouput folder###
    # Set up two columns for input folder and output folder inputs
    # col1, col2 = st.columns(2)

    # with col1:
    #     # Custom label with color and reduced spacing for main dataset folder path
    #     main_dataset_folder = st.text_input("Enter the path to the main dataset folder containing subfolders","./Datasets")

    # with col2:
    #     # Allow user to specify an output folder name, defaulting to "Output"
    #     output_folder_name = st.text_input(
    #         "Enter the output folder name (leave blank for default 'Output'):",
    #         "Output"
    #     )

    # Validate the main dataset folder path
    if main_dataset_folder and os.path.exists(main_dataset_folder):
        #st.success(f"Main dataset folder set to: {main_dataset_folder}")

        # Combine main dataset folder path with output folder name
        output_folder = os.path.join(main_dataset_folder, output_folder_name)

        # Create the output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        #st.success(f"Output folder set to: {output_folder}")
    else:
        st.error("Please provide a valid main dataset folder path.")

    # Specify paths for TIFF and boundary shapefile
    tiff_file_path = os.path.join(main_dataset_folder, "Ceres Imaging/2024-06-17 188633 taps corn NDVI.tif")
    shapefile_roi_folder = os.path.join(main_dataset_folder, "Field_ROI")
    shapefile_roi_path = os.path.join(shapefile_roi_folder, "field_boundary.shp")
    os.makedirs(shapefile_roi_folder, exist_ok=True)

    # Create boundary shapefile from TIFF bounds if it doesn't exist
    if not os.path.exists(shapefile_roi_path):
        with rasterio.open(tiff_file_path) as dataset:
            bounds = dataset.bounds
            crs = dataset.crs
            field_boundary_gdf = gpd.GeoDataFrame(
                {'geometry': [box(bounds.left, bounds.bottom, bounds.right, bounds.top)]},
                crs=crs
            )
            field_boundary_gdf.to_file(shapefile_roi_path, driver="ESRI Shapefile")
            st.success("Boundary shapefile created successfully.")

    # iterarte through folders
    subfolders = [f.name for f in Path(main_dataset_folder).iterdir() if f.is_dir()]

    # Add TAPS Dataset banner on the sidebar
    #st.sidebar.markdown("<h2 style='text-align: center; color: #4CAF50;'>TAPS Dataset</h2>", unsafe_allow_html=True)
    #st.write("Select data folders and upload spatial data files in the slide bar for visualization 📁.")

    #################################################
    ### Main Spatial data input in the slide bar  ###
    #################################################

    

    # # Define the default folder and default shapefile name
    # default_folder_name = "Field_ROI"  # Update to your actual default folder name
    # default_shapefile_name = "field_boundary.shp"  # Update to your actual default shapefile name

    # Field Boundary Shapefile Selection (ROI)
    st.sidebar.write("### Region of Interest (ROI) Selection")
    selected_boundary_folder = st.sidebar.selectbox("Select a folder for field boundary shapefile:",["Field_ROI"] + subfolders, key="boundary")
    selected_boundary = st.sidebar.selectbox("Select a Field Boundary Shapefile:", [""] + [f.name for f in Path(os.path.join(main_dataset_folder, selected_boundary_folder)).rglob("*.shp")], index=0)
    #selected_boundary_folder = st.sidebar.text_input("Select a folder for field boundary shapefile:","Field_ROI", key="boundary")
    #selected_boundary = st.sidebar.text_input("Select a Field Boundary Shapefile:", "field_boundary.shp")
    selected_boundary_path = next((f for f in Path(os.path.join(main_dataset_folder, selected_boundary_folder)).rglob("*.shp") if f.name == selected_boundary), None)

    # Create two columns for checkbox and symbology settings
    col1, col2 = st.sidebar.columns([1, 2])

    # Checkbox for toggling visibility of Field Boundary layer in the first column
    with col1:
        toggle_boundary = st.checkbox("Display", value=True, key="toggle_boundary")

    # Symbology settings for field boundary shapefile in the second column
    with col2:
        boundary_expander = st.expander("🔧 🎨 ")
        with boundary_expander:
            boundary_color = st.color_picker("Line Color", "#FF0000", key="boundary_color")  # Default red
            boundary_weight = st.slider("Line Weight", 1, 10, 2, key="boundary_weight")
            boundary_opacity = st.slider("Fill Opacity", 0.0, 1.0, 0.0, key="boundary_opacity")


    # Shapefile Selection
    st.sidebar.write("### Plot Boundaries Selection")
    selected_shapefile_folder = st.sidebar.selectbox("Select a folder for shapefile data:", ["Plot boundaries"] + subfolders, key="shapefile")
    selected_shapefile = st.sidebar.selectbox("Select a Shapefile:", [""] + [f.name for f in Path(os.path.join(main_dataset_folder, selected_shapefile_folder)).rglob("*.shp")], index=0)
    selected_shapefile_path = next((f for f in Path(os.path.join(main_dataset_folder, selected_shapefile_folder)).rglob("*.shp") if f.name == selected_shapefile), None)

    # Create two columns for checkbox and symbology settings
    col1, col2 = st.sidebar.columns([1, 2])

    # Checkbox for toggling visibility of Field Boundary layer in the first column
    with col1:
        toggle_shapefile = st.checkbox("Display", value=True, key="toggle_shapefile")

    # Symbology settings for field boundary shapefile in the second column
    with col2:
        shapefile_expander = st.expander("🔧 🎨 ")
        with shapefile_expander:
            shapefile_color = st.color_picker("Line Color", "#FF0000", key="shapefile_color")  # Default red
            shapefile_weight = st.slider("Line Weight", 1, 10, 2, key="shapefile_weight")
            shapefile_opacity = st.slider("Fill Opacity", 0.0, 1.0, 0.0, key="shapefile_opacity")

    # TIFF File Selection
    st.sidebar.write("### Imagery File Selection")
    selected_tiff_folder = st.sidebar.selectbox("Select a folder for TIFF data:", [""] + subfolders, key="tiff_folder")
    selected_tiff = st.sidebar.selectbox("Select a TIFF file:", [""] + [f.name for f in Path(os.path.join(main_dataset_folder, selected_tiff_folder)).rglob("*.tif")], index=0, key="selected_tiff")
    selected_tiff_path = next((f for f in Path(os.path.join(main_dataset_folder, selected_tiff_folder)).rglob("*.tif") if f.name == selected_tiff), None)
    # Create two columns for the checkbox and symbology settings
    col1, col2 = st.sidebar.columns([1, 2])
    # Checkbox for toggling visibility of TIFF Layer in the first column
    with col1:
        toggle_tiff = st.checkbox("Display", value=True, key="toggle_tiff")
    # Symbology settings for TIFF file in the second column
    with col2:
        tiff_expander = st.expander("🔧 🏞️ ")
        with tiff_expander:
            tiff_colormap = st.selectbox("Colormap", ["viridis", "jet", "plasma", "cividis", "magma"], index=0, key="tiff_colormap")


    # Display Google Hybrid Imagery Map with ROI drawing tools
    m = leafmap.Map(center=[39.0, -98.0], zoom=5)
    m.add_basemap("HYBRID")

    # Initialize variable to store combined bounds
    layer_bounds = None

    # Check if a shapefile is selected and load it
    if toggle_shapefile and selected_shapefile_path and selected_shapefile_path.exists():
        shapefile_gdf = gpd.read_file(selected_shapefile_path)
        m.add_gdf(shapefile_gdf, layer_name="Selected Shapefile", style={"color": shapefile_color, "weight": shapefile_weight, "fillOpacity": shapefile_opacity})
        shapefile_bounds = shapefile_gdf.total_bounds
        layer_bounds = shapefile_bounds if layer_bounds is None else [
            min(layer_bounds[0], shapefile_bounds[0]),
            min(layer_bounds[1], shapefile_bounds[1]),
            max(layer_bounds[2], shapefile_bounds[2]),
            max(layer_bounds[3], shapefile_bounds[3]),
        ]

    # Add selected field boundary shapefile to map
    if toggle_boundary and selected_boundary_path and selected_boundary_path.exists():
        boundary_gdf = gpd.read_file(selected_boundary_path)
        m.add_gdf(boundary_gdf, layer_name="Field Boundary", style={"color": boundary_color, "weight": boundary_weight, "fillOpacity": boundary_opacity})
        boundary_bounds = boundary_gdf.total_bounds
        layer_bounds = boundary_bounds if layer_bounds is None else [
            min(layer_bounds[0], boundary_bounds[0]),
            min(layer_bounds[1], boundary_bounds[1]),
            max(layer_bounds[2], boundary_bounds[2]),
            max(layer_bounds[3], boundary_bounds[3]),
        ]

    # Check if a TIFF file is selected and load it
    if selected_tiff_path and selected_tiff_path.exists() and toggle_tiff:
        with rasterio.open(str(selected_tiff_path)) as tiff:
            m.add_raster(str(selected_tiff_path), layer_name="Selected TIFF Overlay", colormap=tiff_colormap)
            tiff_bounds = tiff.bounds
            layer_bounds = [tiff_bounds.left, tiff_bounds.bottom, tiff_bounds.right, tiff_bounds.top] if layer_bounds is None else [
                min(layer_bounds[0], tiff_bounds.left),
                min(layer_bounds[1], tiff_bounds.bottom),
                max(layer_bounds[2], tiff_bounds.right),
                max(layer_bounds[3], tiff_bounds.top),
            ]

    ###########################
    ### Tabular data display ###
    ############################

    # Sidebar for displaying tabular data and toggling shapefile display
    st.sidebar.write("### Display Tabular Data")

    # Refresh button to update the list of shapefiles in the Output folder
    if st.sidebar.button("Refresh Shapefiles"):
        st.session_state['output_files'] = list(Path(output_folder).rglob("*.shp"))

    # Check if the session state for output files exists; if not, initialize it
    if 'output_files' not in st.session_state:
        st.session_state['output_files'] = list(Path(output_folder).rglob("*.shp"))

    # Loop through each shapefile and display toggle and symbology options
    for shp_file in st.session_state['output_files']:
        toggle_shp = st.sidebar.checkbox(f"Display {shp_file.stem}", value=False)
        symbology_expander = st.sidebar.expander(f"🔧 🎨")
        
        with symbology_expander:
            color = st.color_picker(f"Point Color for ", "#0000FF")
            weight = st.slider(f"Point Weight for ", 1, 10, 2)
            opacity = st.slider(f"Fill Opacity for ", 0.0, 1.0, 0.6)
            point_size = st.slider(f"Point Size for ", 1, 10, 4)  # Moved here for individual control
            
        # If the shapefile is toggled on, add each point to the map with custom styling
        if toggle_shp:
            gdf = gpd.read_file(shp_file)

            # Add each point from the shapefile to the Folium map with custom styling
            for _, row in gdf.iterrows():
                folium.CircleMarker(
                    location=[row.geometry.y, row.geometry.x],
                    radius=point_size,             # Size of the point
                    color=color,                   # Outline color
                    fill=True,
                    fill_color=color,              # Fill color
                    fill_opacity=opacity,          # Fill opacity
                    weight=weight                  # Border weight
                ).add_to(m)
                boundary_bounds = boundary_gdf.total_bounds
                layer_bounds = boundary_bounds if layer_bounds is None else [
                min(layer_bounds[0], boundary_bounds[0]),
                min(layer_bounds[1], boundary_bounds[1]),
                max(layer_bounds[2], boundary_bounds[2]),
                max(layer_bounds[3], boundary_bounds[3]),
                ]

    # Map display and file details section
    #st.markdown("<h3 style='text-align: center; color: #6c757d;'> Map Display </h3>", unsafe_allow_html=True)

    # Create a single centered column for the button and map
    col2 = st.columns([1])[0]

    # Centering the "Recenter/Zoom to Layer" button and Google Earth text
    with col2:
        # Centered title for Google Earth Hybrid Imagery
        st.markdown("<h5 style='text-align: center; color: #6c757d;'> Google Earth Hybrid Imagery </h6>", unsafe_allow_html=True)

        # Centered button for recentering map
        if st.button("Recenter/Zoom to Layer") and layer_bounds:
            m.zoom_to_bounds(layer_bounds)
        
        # Display the map
        st_folium(m, width=1400, height=700)



    # Load and display shapefile if selected
    if selected_shapefile_path and selected_shapefile_path.exists():
        # Read the shapefile data
        st.write("### File Details")
        shapefile_gdf = gpd.read_file(selected_shapefile_path)
        st.write("**Shapefile Data Preview**")
        st.write("**Shape (Rows, Columns):**", shapefile_gdf.shape)
        st.dataframe(shapefile_gdf, height=250, use_container_width=True)

        # Organize preview and details in three columns
        col1, col2, col3 = st.columns([1, 1, 1])

        # Descriptive Statistics
        with col1:
            with st.expander("Descriptive Statistics"):
                st.write(shapefile_gdf.describe())

        # Column Names and Data Types
        with col2:
            with st.expander("Column Names and Data Types"):
                st.write(shapefile_gdf.dtypes)

        # Null Values in Shapefile Data
        with col3:
            with st.expander("Null Values in Shapefile Data"):
                st.write(shapefile_gdf.isnull().sum())

    # Load and display field boundary data if selected
    if selected_boundary_path and selected_boundary_path.exists():
        boundary_gdf = gpd.read_file(selected_boundary_path)
        st.write("**Field Boundary Data Preview**")
        st.write("**Shape (Rows, Columns):**", boundary_gdf.shape)
        st.dataframe(boundary_gdf, use_container_width=True)

    # Load and display TIFF file metadata if selected
    if selected_tiff_path and selected_tiff_path.exists():
        with rasterio.open(selected_tiff_path) as tiff:
            st.write("**TIFF File Metadata**")
            with st.expander("TIFF File Metadata"):
                metadata = {key: value for key, value in tiff.profile.items()}
                st.write(" | ".join([f"**{k.capitalize()}**: {v}" for k, v in metadata.items()]))

            with st.expander("TIFF File Image Preview"):
                fig, ax = plt.subplots(figsize=(3, 5))
                show(tiff.read(1), cmap=tiff_colormap, ax=ax)
                plt.title(f"TIFF Image: {selected_tiff}")
                plt.axis("off")
                st.pyplot(fig)

    # Define output folder for dynamically loaded shapefiles
    output_folder = os.path.join(os.path.dirname(__file__), "Output")  
    if not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)

    ###############################
    ### Tabular data processing###
    ###############################

    # st.markdown("<h3 style='text-align: center; color: #6c757d;'> Display Tabular Data </h3>", unsafe_allow_html=True)

    # st.write("This page is for uploading and analyzing tabular data files.")

    # uploaded_files = st.file_uploader(
    #     "Upload one or more tabular files (CSV, Excel, or TXT)", 
    #     type=["csv", "xls", "xlsx", "txt"], 
    #     accept_multiple_files=True
    # )

    # if uploaded_files:
    #     file_names = [file.name for file in uploaded_files]
    #     selected_file = st.selectbox("Choose a file to display:", file_names)
    #     file_obj = next(file for file in uploaded_files if file.name == selected_file)

    #     file_extension = file_obj.name.split('.')[-1].lower()
    #     base_filename = os.path.splitext(file_obj.name)[0]

    #     if file_extension == "csv":
    #         initial_df = pd.read_csv(file_obj, header=None)
    #     elif file_extension in ["xls", "xlsx"]:
    #         xls = pd.ExcelFile(file_obj)
    #         sheet_names = xls.sheet_names
    #         selected_sheet = st.selectbox("Choose a sheet to display:", sheet_names)
    #         initial_df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=None)
    #     elif file_extension == "txt":
    #         initial_df = pd.read_csv(file_obj, delimiter='\t', header=None)
    #     else:
    #         st.error(f"Unsupported file format: {file_extension}")
    #         st.stop()

    #     st.write("### Initial Preview of the File (First 10 Rows)")
    #     st.dataframe(initial_df.head(10))

    #     header_option = st.radio(
    #         "Select header configuration:",
    #         options=["Single header row", "Multiple header rows",  "Merge multiple rows for header"]
    #     )


    #     if header_option == "Single header row":
    #         header_row = st.number_input(
    #             "Select the row number to use as header (0-indexed):",
    #             min_value=0,
    #             max_value=len(initial_df) - 1,
    #             value=0
    #         )
    #         file_obj.seek(0)
    #         if file_extension == "csv":
    #             df = pd.read_csv(file_obj, header=header_row)
    #         elif file_extension in ["xls", "xlsx"]:
    #             df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=header_row)
    #         elif file_extension == "txt":
    #             df = pd.read_csv(file_obj, delimiter='\t', header=header_row)

    #     elif header_option == "Multiple header rows":
    #         header_rows = st.multiselect(
    #             "Select the row numbers to use as header (0-indexed):",
    #             options=list(range(len(initial_df))),
    #             default=[0, 1]
    #         )
    #         file_obj.seek(0)
    #         if file_extension == "csv":
    #             temp_df = pd.read_csv(file_obj, header=list(header_rows))
    #         elif file_extension in ["xls", "xlsx"]:
    #             temp_df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=list(header_rows))
    #         elif file_extension == "txt":
    #             temp_df = pd.read_csv(file_obj, delimiter='\t', header=list(header_rows))
            
    #         # Merge the selected header rows into a single header
    #         df = temp_df.copy()
    #         df.columns = [" ".join([str(col).strip() for col in multi_col if pd.notna(col)]) for multi_col in zip(*df.columns)]

    #     elif header_option == "Merge multiple rows for header":
    #         num_header_rows = st.number_input(
    #             "Select the number of rows to merge for column headers:",
    #             min_value=1,
    #             max_value=5,
    #             value=1
    #         )
    #         file_obj.seek(0)
            
    #         # Read the file to extract the header rows for merging
    #         if file_extension == "csv":
    #             temp_df = pd.read_csv(file_obj, header=list(range(num_header_rows)))
    #         elif file_extension in ["xls", "xlsx"]:
    #             temp_df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=list(range(num_header_rows)))
    #         elif file_extension == "txt":
    #             temp_df = pd.read_csv(file_obj, delimiter='\t', header=list(range(num_header_rows)))
            
    #         # Merge headers with an underscore and remove leading underscores if present
    #         merged_header = temp_df.columns.to_frame().T.fillna("").astype(str).agg("_".join).str.strip("_")
            
    #         # Reset the file pointer again to read the full data with the merged header
    #         file_obj.seek(0)
    #         if file_extension == "csv":
    #             df = pd.read_csv(file_obj, header=list(range(num_header_rows)))
    #         elif file_extension in ["xls", "xlsx"]:
    #             df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=list(range(num_header_rows)))
    #         elif file_extension == "txt":
    #             df = pd.read_csv(file_obj, delimiter='\t', header=list(range(num_header_rows)))

    #         # Set the merged header as the dataframe columns
    #         df.columns = merged_header

        
    #     # Remove duplicate columns, keeping only the first occurrence
    #     df = df.loc[:, ~df.columns.duplicated()]

    #     st.write("### Data Preview with Selected Header Configuration")
    #     st.write(f"**Shape (Rows, Columns):** {df.shape}")

    #     # Make a copy of the DataFrame to apply modifications
    #     df_modified = df.copy()

    #         # Expander for renaming columns with a multiselect option
    #     with st.expander("Rename Columns"):
    #         selected_columns = st.multiselect("Select columns to rename:", options=df.columns)
    #         col_rename_dict = {}

    #         for col in selected_columns:
    #             new_name = st.text_input(f"Rename '{col}' to:", value=col)
    #             col_rename_dict[col] = new_name

    #         # Apply renaming only to selected columns
    #         if col_rename_dict:
    #             df_modified = df_modified.rename(columns=col_rename_dict)

    #     # Expander for removing columns
    #     with st.expander("Remove Columns"):
    #         columns_to_remove = st.multiselect("Select columns to remove:", options=df_modified.columns)
    #         if columns_to_remove:
    #             df_modified = df_modified.drop(columns=columns_to_remove)

    #     # Expander for removing rows
    #     with st.expander("Remove Rows"):
    #         # Select rows to remove by index
    #         rows_to_remove = st.multiselect("Select rows to remove by index:", options=df_modified.index.tolist())
    #         if rows_to_remove:
    #             df_modified = df_modified.drop(index=rows_to_remove)


    #     st.write("#### Modified Data Preview")
    #     st.dataframe(df_modified, height=250, use_container_width=True)

    #     st.write("### Additional Data Insights")

    #     col1, col2, col3 = st.columns([2, 2, 2])

    #     with col1:
    #         with st.expander("Descriptive Statistics"):
    #             st.dataframe(df_modified.describe(), use_container_width=True)

    #     with col2:
    #         with st.expander("Column Names and Data Types"):
    #             st.dataframe(df_modified.dtypes.to_frame(name="Data Type"), use_container_width=True)

    #     with col3:
    #         with st.expander("Null Values in Data"):
    #             st.dataframe(df_modified.isnull().sum().to_frame(name="Null Count"), use_container_width=True)

    #     col1, col2, col3 = st.columns([10,5,10])

    #     df_modified.columns = df_modified.columns.str.strip()

    #     if 'Long' in df_modified.columns and 'Lat' in df_modified.columns:
    #         df_modified['geometry'] = df_modified.apply(lambda row: Point(row['Long'], row['Lat']), axis=1)
    #         geo_df = gpd.GeoDataFrame(df_modified, geometry='geometry', crs="EPSG:4326")
    #         if selected_boundary_path and selected_boundary_path.exists():
    #             boundary_gdf = gpd.read_file(selected_boundary_path)

    #         #boundary_gdf = gpd.read_file("Field_ROI/Field_boundary.shp")

    #         geo_df = gpd.sjoin(geo_df, boundary_gdf, how="inner", predicate="within")
    #         geo_df = geo_df[df_modified.columns]

    #         with col1:
    #             if st.button("Download Modified Data as Shapefile ⬇️", key="download_shapefile"):
    #                 shapefile_name = f"{base_filename}_{selected_sheet}_modified.shp"
    #                 save_path = os.path.join(output_folder, shapefile_name)
    #                 geo_df.to_file(save_path, driver='ESRI Shapefile')
    #                 st.success(f"Filtered data has been saved as a shapefile: {shapefile_name}")
    #     else:
    #         st.error("Latitude and longitude columns are required to convert to a GeoDataFrame.")

    #     with col3:
    #         if st.button("Download Modified Data as CSV file ⬇️", key="save_csv_file"):
    #             cleaned_file_name = f"{base_filename}_{selected_sheet}_modified.{file_extension}"
    #             save_path = os.path.join(output_folder, cleaned_file_name)
                
    #             if file_extension == "csv":
    #                 data = geo_df.to_csv(index=False).encode('utf-8')
    #                 mime_type = 'text/csv'
    #                 geo_df.to_csv(save_path, index=False)
    #             elif file_extension in ["xls", "xlsx"]:
    #                 output = BytesIO()
    #                 with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    #                     geo_df.to_excel(writer, sheet_name="Sheet1", index=False)
    #                 data = output.getvalue()
    #                 mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    #                 with pd.ExcelWriter(save_path, engine="xlsxwriter") as writer:
    #                     geo_df.to_excel(writer, sheet_name="Sheet1", index=False)
    #             elif file_extension == "txt":
    #                 data = geo_df.to_csv(index=False, sep='\t').encode('utf-8')
    #                 mime_type = 'text/plain'
    #                 geo_df.to_csv(save_path, sep='\t', index=False)
            

    #             st.success(f"File successfully saved in the output folder: {save_path}")


elif page == "Data Analysis":
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'> TAPS Data Analysis Dashboard </h1>", unsafe_allow_html=True)
    st.markdown("<h5 style='text-align: center; color: #6c757d;'> Interpolation, Zonal Statsitics and Clustering Analysis </h3>", unsafe_allow_html=True)
    color_scheme = "RdYlGn"
    page1 = st.sidebar.selectbox("Choose a Tool",["Data Interpolation", "Zonal Statistics", "Clustering"])
    if page1 == "Data Interpolation":
        # Load data
        st.header("Upload Files")
        file_path = st.file_uploader("Upload Excel File for Data", type="xlsx")
        shapefile_path = './Datasets/Field_ROI/Field_boundary.shp'
        
        
        if file_path and shapefile_path:
            
            # col1,col2 = st.columns([0.2,0.8])
            # with col1:# Extract the shapefile and load it
                shapefile_gdf = gpd.read_file(shapefile_path)
                
                # Get available sheet names
                sheet_names = pd.ExcelFile(file_path).sheet_names
                sheet_name = st.selectbox("Select Data Sheet", sheet_names, index = None)
                if sheet_name is not None:
                    # Load selected sheet
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    # Define interpolation function
                    def interpolate_grid(df, grid_x, grid_y, value_col, method="linear"):
                        if method == "idw":
                            def inverse_distance_weighting(x, y, z, xi, yi, power=2):
                                distances = np.sqrt((x - xi)**2 + (y - yi)**2)
                                weights = 1 / (distances**power)
                                weights /= weights.sum()
                                return np.sum(weights * z)

                            grid_z = np.empty(grid_x.shape)
                            for i in range(grid_x.shape[0]):
                                for j in range(grid_x.shape[1]):
                                    grid_z[i, j] = inverse_distance_weighting(
                                        df['Lat'], df['Long'], df[value_col],
                                        grid_x[i, j], grid_y[i, j]
                                    )
                        else:
                            grid_z = griddata(
                                (df['Lat'], df['Long']), df[value_col],
                                (grid_x, grid_y), method=method
                            )
                        return grid_z
                    
                    # Define column for values (assuming 'pH Avg.' column exists)
                    value_col = st.selectbox("Select a value column",df.columns)
                    # Select interpolation method
                    interpolation_method = st.selectbox("Select Interpolation Method", ["linear", "cubic", "nearest", "idw"], index =None)
                    #interpolation_method = st.selectbox("Select Interpolation Method", ["linear", "cubic", "nearest", "idw"], index = None)

                    if interpolation_method is not None:
                        #Define grid for interpolation
                        grid_x, grid_y = np.mgrid[
                            df['Lat'].min():df['Lat'].max():100j,
                            df['Long'].min():df['Long'].max():100j
                        ]
                        # Interpolate the values
                        grid_z = interpolate_grid(df, grid_x, grid_y, value_col, method=interpolation_method)

                        # Define transformation and metadata for in-memory raster
                        transform = rasterio.transform.from_origin(
                            df['Long'].min(), df['Lat'].max(),
                            (df['Long'].max() - df['Long'].min()) / 100,
                            (df['Lat'].max() - df['Lat'].min()) / 100
                        )
                        
                        metadata = {
                            'driver': 'GTiff',
                            'height': grid_z.shape[0],
                            'width': grid_z.shape[1],
                            'count': 1,
                            'dtype': 'float32',
                            'crs': 'EPSG:4326',
                            'transform': transform
                        }
                        output_path = f'./Datasets/Output/{value_col}_{interpolation_method}.tif'
                        temp_path = 'temp_interpolated_surface.tif'
                        with rasterio.open(temp_path, 'w', **metadata) as dst:
                            dst.write(np.nan_to_num(grid_z, nan=0).astype('float32'), 1)
                            dst.nodata = 0

                        # Clip TIFF file with shapefile
                        shapes = [feature["geometry"] for feature in shapefile_gdf.__geo_interface__["features"]]
                        with rasterio.open(temp_path) as src:
                            out_image, out_transform = mask(src, shapes, crop=True)
                            out_meta = src.meta.copy()

                            # Update metadata and save clipped raster
                            out_meta.update({
                                "driver": "GTiff",
                                "height": out_image.shape[1],
                                "width": out_image.shape[2],
                                "transform": out_transform
                            })

                            with rasterio.open(output_path, "w", **out_meta) as dest:
                                dest.write(out_image)
                                dest.nodata = 0

                            #st.success(f"Clipped TIFF file saved at {output_path}")
                    # Set up the columns with specific width proportions
                        col11, col12, col13 = st.columns([0.25, 0.5, 0.25])

                        # Add content to the second column only
                        with col12:
                        #     # Display the clipped raster image
                            #st.header("Clipped Raster Image")
                            fig, ax = plt.subplots(figsize=(10, 3))  # Adjust figure size as needed
                            im = ax.imshow(out_image[0], cmap='viridis')
                            
                            # Add colorbar and labels
                            cbar = plt.colorbar(im, ax=ax, label=f"{value_col} Value")
                            ax.set_title("Interpolated pH Raster (Clipped)")
                            # Remove x and y axis values
                            ax.set_xticks([])
                            ax.set_yticks([])
                            # Display the plot in Streamlit
                            st.pyplot(fig)


                        # Provide download option for the output file
                        with open(output_path, "rb") as file:
                            tiff_data = file.read()

                        st.download_button(
                            label="Download Clipped TIFF File",
                            data=tiff_data,
                            file_name="pHclipped12456.tif",
                            mime="image/tiff"
                        )

    elif page1 == "Zonal Statistics":
        # Validate the folder path
        if main_dataset_folder:
            if os.path.exists(main_dataset_folder):
                print(f"Main dataset folder set to: {main_dataset_folder}")
            else:
                st.error("The folder path does not exist. Please enter a valid path.")

        # List subfolders for shapefile and TIFF selection separately
        subfolders = [f.name for f in Path(main_dataset_folder).iterdir() if f.is_dir()]

        selected_shapefile_folder = st.selectbox("Select a folder for shapefile data:", subfolders, index=None, key="shp")
        selected_tiff_folder = st.selectbox("Select a folder for TIFF data:", subfolders, index=None, key="tiff")
    
        # Check if a folder has been selected
        if selected_tiff_folder:
            # Get paths for the selected folders
            tiff_folder_path = os.path.join(main_dataset_folder, selected_tiff_folder)
            
            # Load TIFF files
            selected_tiff_files = [f.name for f in Path(tiff_folder_path).rglob("*.tif")]
            shapefile_folder_path = os.path.join(main_dataset_folder, selected_shapefile_folder)
            selected_shapefiles = [f.name for f in Path(shapefile_folder_path).rglob("*.shp")]
            if not selected_tiff_files:
                st.error("No TIFF files found in the selected folder.")
            elif not selected_shapefiles:
                st.error("No Shapefile found in the selected folder.")
            else:
                selected_shapefile = st.sidebar.selectbox("Select a Shapefile:", selected_shapefiles, index=None)
                selected_shapefile_file = next((f for f in Path(shapefile_folder_path).rglob("*.shp") if f.name == selected_shapefile), None)
                selected_tiff = st.sidebar.selectbox("Select a TIFF file:", sorted(selected_tiff_files), index=None)
                selected_tiff_file = next((f for f in Path(tiff_folder_path).rglob("*.tif") if f.name == selected_tiff), None)

                if selected_tiff_file and selected_shapefile_file:
                    # Load the shapefile and ensure Plot_ID is treated as a string
                    shapefile_gdf = gpd.read_file(selected_shapefile_file)
                    shapefile_gdf["Plot_ID"] = shapefile_gdf["Plot_ID"].astype(str)

                    # Initialize or update the main dataframe with mean NDVI for each TIFF file
                    if "main_df" not in st.session_state:
                        st.session_state.main_df = shapefile_gdf.copy()

                    def calculate_mean_values(gdf, tiff_path, column_name):
                        """Calculate mean NDVI values for each plot based on the selected TIFF."""
                        with rasterio.open(tiff_path) as src:
                            means = []
                            for geom in gdf.geometry:
                                mask = geometry_mask([geom], transform=src.transform, invert=True, out_shape=(src.height, src.width))
                                data = src.read(1, masked=True)
                                mean_value = np.mean(data[mask])
                                means.append(mean_value)
                            gdf[column_name] = means
                        return gdf
                            
                    # Assuming 'selected_tiff_file' is a Path object
                    if selected_tiff_file.stem.endswith("NDVI"):
                        column_name = f"mean_{selected_tiff_file.stem[-4:]}_{selected_tiff_file.stem[:10]}"  # Change 'NDVI_Value' to your desired column name
                    elif selected_tiff_file.stem.endswith("MCARI2"):
                        column_name = f"mean_{selected_tiff_file.stem[-6:]}_{selected_tiff_file.stem[:10]}"
                    else:
                        column_name = f"mean_{selected_tiff_file.stem}"

                    # # Add mean NDVI column only if it doesn't already exist
                    # column_name = f"mean_{selected_tiff_file.stem[-4:]}_{selected_tiff_file.stem[:10]}"  # Use the stem of the TIFF filename
                    if column_name not in st.session_state.main_df.columns:
                        st.session_state.main_df = calculate_mean_values(st.session_state.main_df, str(selected_tiff_file), column_name)

                    # Dropdown for selecting a column to highlight
                    selected_column = st.selectbox("Select Column to Highlight", st.session_state.main_df.columns, index = 2)

                    # Get unique values from the selected column
                    unique_values = st.session_state.main_df[selected_column].unique()
                    selected_value = st.selectbox("Select Value to Highlight", unique_values, index=None)

                    # Columns Layout for plot and heatmap, ensuring consistent size
                    col1, col2 = st.columns(2)

                    # Set consistent size for both plots
                    fig_size = (6, 6)  # Adjust this value if needed for perfect alignment

                    with col1:
                        st.markdown(f"<h3 style='text-align: center;'>TIFF: {column_name[5:]}</h3>", unsafe_allow_html=True)
                        fig, ax = plt.subplots(figsize=fig_size)  # Fixed size
                        
                        with rasterio.open(str(selected_tiff_file)) as src:
                            show(src, ax=ax, cmap=color_scheme)
                        
                        shapefile_gdf.boundary.plot(ax=ax, edgecolor="black", linewidth=1.2)

                        # Plotting all polygons
                        shapefile_gdf.plot(ax=ax, edgecolor='black', facecolor='none', linewidth=1)  # Outline all polygons

                        # Annotating all polygons
                        for _, row in shapefile_gdf.iterrows():
                            # Get the centroid of the polygon for annotation placement
                            centroid = row.geometry.centroid
                            # Annotate with the value of the selected column
                            ax.annotate(
                                row[selected_column], 
                                xy=(centroid.x, centroid.y), 
                                horizontalalignment='center', 
                                verticalalignment='center', 
                                fontsize=8,  # Adjust font size if needed
                                color='black',  # Change text color if needed
                                weight='bold'  # Make the text bold if desired
                            )

                        # If a specific value is selected, highlight its boundaries
                        if selected_value:
                            selected_polygons = shapefile_gdf[shapefile_gdf[selected_column] == selected_value]
                            selected_polygons.boundary.plot(ax=ax, edgecolor="blue", linewidth=2.5)
                        
                        # Removing extra margins
                        ax.set_adjustable('box')
                        ax.set_aspect('auto')  # Keep aspect ratio constant
                        st.pyplot(fig)


                    with col2:
                        st.markdown(f"<h3 style='text-align: center;'>Mean {column_name[5:]} Plot values</h3>", unsafe_allow_html=True)
                        heatmap_fig, ax = plt.subplots(figsize=fig_size)  # Fixed size
                        shapefile_gdf = calculate_mean_values(shapefile_gdf, selected_tiff_file, column_name)
                        shapefile_gdf.plot(column=column_name, cmap=color_scheme, legend=True, ax=ax)
                    
                        for _, row in shapefile_gdf.iterrows():
                            centroid = row.geometry.centroid
                            ax.annotate(
                                row[selected_column], 
                                xy=(centroid.x, centroid.y), 
                                horizontalalignment='center', 
                                verticalalignment='center', 
                                fontsize=8,  # Adjust font size if needed
                                color='black',  # Change text color if needed
                                weight='bold'  # Make the text bold if desired
                            )
                        if selected_value:
                            shapefile_gdf[shapefile_gdf[selected_column] == selected_value].plot(ax=ax, edgecolor="blue", linewidth=2.5, facecolor="none")

                        # Removing extra margins
                        ax.set_adjustable('box')
                        ax.set_aspect('auto')  # Keep aspect ratio constant
                        st.pyplot(heatmap_fig)

                    # Function to save plots as a single JPG
                    def save_combined_plot(selected_tiff_file, column_name, selected_value):
                        fig, axs = plt.subplots(1, 2, figsize=(12, 6))  # Adjust size as needed

                        # Plot for col1 (TIFF)
                        ax1 = axs[0]
                        with rasterio.open(str(selected_tiff_file)) as src:
                            show(src, ax=ax1, cmap=color_scheme)
                        shapefile_gdf.boundary.plot(ax=ax1, edgecolor="black", linewidth=1.2)

                        # Plotting all polygons and annotating
                        shapefile_gdf.plot(ax=ax1, edgecolor='black', facecolor='none', linewidth=1)  # Outline all polygons
                        for _, row in shapefile_gdf.iterrows():
                            centroid = row.geometry.centroid
                            ax1.annotate(
                                row[selected_column], 
                                xy=(centroid.x, centroid.y), 
                                horizontalalignment='center', 
                                verticalalignment='center', 
                                fontsize=8,  # Adjust font size if needed
                                color='black',  # Change text color if needed
                                weight='bold'  # Make the text bold if desired
                            )

                        # If a specific value is selected, highlight its boundaries
                        if selected_value:
                            selected_polygons = shapefile_gdf[shapefile_gdf[selected_column] == selected_value]
                            selected_polygons.boundary.plot(ax=ax1, edgecolor="blue", linewidth=2.5)
                        
                        ax1.set_title(f'TIFF: {column_name[5:]}')

                        # Plot for col2 (Mean Plot)
                        ax2 = axs[1]
                        heatmap_data = calculate_mean_values(shapefile_gdf, selected_tiff_file, column_name)
                        heatmap_data.plot(column=column_name, cmap=color_scheme, legend=True, ax=ax2)
    # Plotting all polygons and annotating
                        shapefile_gdf.plot(ax=ax2, edgecolor='black', facecolor='none', linewidth=1)  # Outline all polygons
                        for _, row in shapefile_gdf.iterrows():
                            centroid = row.geometry.centroid
                            ax2.annotate(
                                row[selected_column], 
                                xy=(centroid.x, centroid.y), 
                                horizontalalignment='center', 
                                verticalalignment='center', 
                                fontsize=8,  # Adjust font size if needed
                                color='black',  # Change text color if needed
                                weight='bold'  # Make the text bold if desired
                            )

                        # Highlighting selected value in the mean plot
                        if selected_value:
                            heatmap_data[heatmap_data[selected_column] == selected_value].plot(ax=ax2, edgecolor="blue", linewidth=2.5, facecolor="none")
                        
                        ax2.set_title(f'Mean {column_name[5:]} Plot values')

                        plt.tight_layout()

                        # Save the combined figure as a JPG
                        jpg_buffer = io.BytesIO()
                        plt.savefig(jpg_buffer, format='jpg', bbox_inches='tight')
                        plt.close(fig)  # Close the figure to free up memory
                        jpg_buffer.seek(0)
                        return jpg_buffer

                    # Option to download the combined plots as JPG
                    if st.button(f"Download combined plot"):
                        jpg_image = save_combined_plot(selected_tiff_file, column_name, selected_value)

                        st.download_button(
                            label=f"{column_name[5:]} combined plot.jpeg",
                            data=jpg_image,
                            file_name=f"{column_name[5:]} combined plot.jpeg",
                            mime="image/jpeg"
                        )


                    # Mean NDVI Bar Chart with Interactive Selection
                    st.markdown(f"<h3 style='text-align: center;'>Mean {column_name[5:]} values per {selected_column}<v/h3>", unsafe_allow_html=True)

                    # Group by selected column and calculate the mean for the column_name
                    mean_values = st.session_state.main_df.groupby(selected_column)[column_name].mean().reset_index()

                    # Create the bar plot with the mean values
                    fig = px.bar(
                        mean_values,  # Use the grouped DataFrame
                        x=selected_column, 
                        y=column_name, 
                        title="", 
                        color=column_name, 
                        color_continuous_scale=color_scheme
                    )

                    fig.update_layout(
                        xaxis_title=selected_column,
                        yaxis_title="Mean NDVI",
                        xaxis_categoryorder="total descending",  # Ensures descending order
                        xaxis_type="category",  # Treats Plot_ID as categorical, removing gaps
                        template="plotly_dark"
                    )

                    # Highlight the selected value in the plot
                    if selected_value:
                        # Get the index of the selected value in the mean_values DataFrame
                        selected_index = mean_values[mean_values[selected_column] == selected_value].index.tolist()
                        
                        # If the selected value exists in the mean_values DataFrame, update selectedpoints
                        if selected_index:
                            fig.update_traces(
                                hovertemplate="Plot ID: %{x}<br>Mean NDVI: %{y:.2f}",
                                selectedpoints=selected_index  # Set the selectedpoints to the index of the selected value
                            )

                    st.plotly_chart(fig, use_container_width=True)

                    # Option to download the plot as an image
                    if st.button("Download Bar Chart as Image"):
                        # Define the filename using column_name
                        filename = f"{column_name}_{selected_column}.png"  # You can change the extension if needed

                        # Set the desired resolution and image size
                        width = 1200  # Width of the image in pixels
                        height = 400  # Height of the image in pixels
                        scale =1  # Scale factor for DPI

                        # Save the figure as an image with specified size and resolution
                        pio.write_image(fig, filename, width=width, height=height, scale=scale)  # This saves the image

                        # Provide a download link
                        with open(filename, "rb") as f:
                            st.download_button(
                                label="Download Image",
                                data=f,
                                file_name=filename,
                                mime="image/png"
                            )


                    # Highlight selected rows in the DataFrame and move them to the top for visualization
                    if selected_value:
                        # Create a boolean mask for the selected value
                        highlighted_rows = st.session_state.main_df[selected_column] == selected_value
                        
                        # Create a new DataFrame with highlighted rows first
                        highlighted_df = st.session_state.main_df[highlighted_rows].copy()
                        other_df = st.session_state.main_df[~highlighted_rows].copy()
                        
                        # Concatenate the highlighted rows with the other rows
                        sorted_df = pd.concat([highlighted_df, other_df], ignore_index=True)
                    else:
                        sorted_df = st.session_state.main_df  # If no value is selected, use the original DataFrame

                    # Function to highlight the entire row
                    def highlight_row(row):
                        if selected_value and row[selected_column] == selected_value:
                            return ['background-color: yellow'] * len(row)  # Highlight the entire row
                        return [''] * len(row)  # No highlight

                    # Display the sorted DataFrame with highlights
                    st.subheader("Data Table")
                    st.dataframe(sorted_df.style.apply(highlight_row, axis=1), height=300)

                    # Option to download the full DataFrame as CSV (without any highlights)
                    csv = st.session_state.main_df.to_csv(index=False).encode('utf-8')

                    if st.button("Save Zonal statistics datafile as CSV"):
                        # Define output paths
                        csv_filename = "Zonal_statistics.csv"
                        output_csv_path = os.path.join(main_dataset_folder, "Output", csv_filename)
                        os.makedirs(os.path.join(main_dataset_folder, "Output"), exist_ok=True)  # Ensure the directory exists
                        st.session_state.main_df.to_csv(output_csv_path, index=False)
                        st.success(f"Zonal statistics data saved as: {csv_filename}")

                        # Check if both Zonal_statistics.csv and Merged_data.csv exist
                        merged_data_path = os.path.join(main_dataset_folder, "Output", "Merged_data.csv")
                        if os.path.exists(merged_data_path) and os.path.exists(output_csv_path):
                            # Load both CSVs
                            df_zonal = pd.read_csv(output_csv_path)
                            df_merged = pd.read_csv(merged_data_path)

                            # Merge both files on 'Plot_ID', keeping only unique columns
                            final_df = pd.merge(df_merged, df_zonal, on="Plot_ID", how="outer", suffixes=('', '_dup'))

                            # Remove duplicate columns by checking for "_dup" suffix
                            duplicate_columns = [col for col in final_df.columns if col.endswith('_dup')]
                            final_df.drop(columns=duplicate_columns, inplace=True)

                            # Optionally, remove additional specific duplicate columns if they exist
                            columns_to_check = ["geometry", "TRT_ID", "Block_ID"]
                            final_df = final_df.loc[:, ~final_df.columns.duplicated()]

                            
                            # Provide a download button for the final merged DataFrame
                            final_csv_filename = "Final_Merged_Data.csv"
                            final_csv_path = os.path.join(main_dataset_folder, "Output", final_csv_filename)
                            final_df.to_csv(final_csv_path, index=False)
                            output_final_csv = final_df.to_csv(index=False)
                            st.success(f"Final merged data saved as: {final_csv_filename}")

                            st.write(pd.read_csv(final_csv_path))
                            st.download_button(
                        label="Download Final_Merged_data to Local Directory",
                        data=output_final_csv,
                        file_name="Final_Merged_Data.csv",
                        mime="text/csv"
                    )
    elif page1== "Clustering":
        # File upload section
        uploaded_file = st.file_uploader("Upload a TIFF file", type=["tif", "tiff"])

        if uploaded_file:
            # Load TIFF file
            with rasterio.open(uploaded_file) as src:
                image = src.read(1)  # Read the first band for analysis
                affine = src.transform

            st.write("Uploaded TIFF file details:")
            st.write(f"Dimensions: {image.shape}")
            show(image, transform=affine)
            
            # Clustering parameters
            num_clusters = st.slider("Number of clusters", min_value=2, max_value=10, value=3)
            data = image[~np.isnan(image)].reshape(-1, 1)  # Reshape to 1D array, remove NaNs
            
            kmeans = KMeans(n_clusters=num_clusters)
            clusters = kmeans.fit_predict(data)
            
            # Reshape back to image dimensions and show results
            cluster_img = np.full(image.shape, np.nan)
            cluster_img[~np.isnan(image)] = clusters
            # Create three columns
            col1a, col2a, col3a = st.columns(3)

            with col2a:  # Use the second column
                fig, ax = plt.subplots(figsize=(6, 2))
                st.subheader("Clustering Result")
                
                # Display the clustering image
                im = ax.imshow(cluster_img, cmap="viridis")
                # Set the size of the x and y tick labels
                ax.tick_params(axis='both', labelsize=8)  # Adjust the size as needed
                ax.set_xticks([])
                ax.set_yticks([])
                # Create and adjust the colorbar
                cbar = plt.colorbar(im, ax=ax)
                cbar.ax.tick_params(labelsize=4)
                st.pyplot(fig)


                        


elif page == "Data Management":

    st.markdown("<h1 style='text-align: center; color: #4CAF50;'> TAPS Tabular Data Input, Cleaning & Integration </h1>", unsafe_allow_html=True)
    st.markdown("<h5 style='text-align: center; color: #6c757d;'> Data cleaning is not just a preprocessing step, but the foundation that robust analytics are built on.</h3>", unsafe_allow_html=True)
    ###Setting input and ouput folder###
    # Set up two columns for input folder and output folder inputs
    #col1, col2 = st.columns(2)

    # with col1:
    #     # Custom label with color and reduced spacing for main dataset folder path
    #     main_dataset_folder = st.text_input("Enter the path to the main dataset folder containing subfolders","./Datasets")

    # with col2:
    #     # Allow user to specify an output folder name, defaulting to "Output"
    #     output_folder_name = st.text_input(
    #         "Enter the output folder name (leave blank for default 'Output'):",
    #         "Output"
    #     )

    # Validate the main dataset folder path
    if main_dataset_folder and os.path.exists(main_dataset_folder):
        #st.success(f"Main dataset folder set to: {main_dataset_folder}")

        # Combine main dataset folder path with output folder name
        output_folder = os.path.join(main_dataset_folder, output_folder_name)

        # Create the output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        #st.success(f"Output folder set to: {output_folder}")
    else:
        st.error("Please provide a valid main dataset folder path.")


    # iterarte through folders
    subfolders = [f.name for f in Path(main_dataset_folder).iterdir() if f.is_dir()]

    ##################################################################
    ######################## Tabular data cleaning  ##################
    ##################################################################

    #st.markdown("<h3 style='text-align: center; color: #6c757d;'> Display Tabular Data </h3>", unsafe_allow_html=True)

    #st.write("This page is for pre-processing tabular data files.")

    uploaded_files = st.file_uploader(
        "Upload one or more tabular files (CSV, Excel, or TXT)", 
        type=["csv", "xls", "xlsx", "txt"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        file_names = [file.name for file in uploaded_files]
        selected_file = st.selectbox("Choose a file to display:", file_names)
        file_obj = next(file for file in uploaded_files if file.name == selected_file)

        file_extension = file_obj.name.split('.')[-1].lower()
        base_filename = os.path.splitext(file_obj.name)[0]

        if file_extension == "csv":
            initial_df = pd.read_csv(file_obj, header=None)
        elif file_extension in ["xls", "xlsx"]:
            xls = pd.ExcelFile(file_obj)
            sheet_names = xls.sheet_names
            selected_sheet = st.selectbox("Choose a sheet to display:", sheet_names)
            initial_df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=None)
        elif file_extension == "txt":
            initial_df = pd.read_csv(file_obj, delimiter='\t', header=None)
        else:
            st.error(f"Unsupported file format: {file_extension}")
            st.stop()
        st.markdown("<h5 style='text-align: center; color: #6c757d;'> Initial Preview </h3>", unsafe_allow_html=True)
        
        st.dataframe(initial_df,height = 250,  use_container_width=True)
        st.markdown("### Header Configuration")
        header_option = st.radio(
            "Select header configuration:",
            options=["Single header row", "Multiple header rows", "Merge multiple rows for header"]
        ) 

        if header_option == "Single header row":
            header_row = st.number_input(
                "Select the row number to use as header (0-indexed):",
                min_value=0,
                max_value=len(initial_df) - 1,
                value=0
            )
            file_obj.seek(0)
            if file_extension == "csv":
                df = pd.read_csv(file_obj, header=header_row)
            elif file_extension in ["xls", "xlsx"]:
                df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=header_row)
            elif file_extension == "txt":
                df = pd.read_csv(file_obj, delimiter='\t', header=header_row)
            st.write("### Single header row applied")

        elif header_option == "Multiple header rows":
            header_rows = st.multiselect(
                "Select the row numbers to use as header (0-indexed):",
                options=list(range(len(initial_df))),
                default=[1, 3]
            )
            file_obj.seek(0)
            if file_extension == "csv":
                temp_df = pd.read_csv(file_obj, header=None)
            elif file_extension in ["xls", "xlsx"]:
                temp_df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=None)
            elif file_extension == "txt":
                temp_df = pd.read_csv(file_obj, delimiter='\t', header=None)
            
            # Extract only the selected header rows
            selected_headers = temp_df.iloc[header_rows]
            
            # Merge the selected header rows into a single header
            merged_header = [
                " ".join([str(val).strip() for val in selected_headers[col] if pd.notna(val)])
                for col in selected_headers
            ]
            
            # Read the full data using the merged header
            file_obj.seek(0)
            if file_extension == "csv":
                df = pd.read_csv(file_obj, header=list(header_rows))
            elif file_extension in ["xls", "xlsx"]:
                df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=list(header_rows))
            elif file_extension == "txt":
                df = pd.read_csv(file_obj, delimiter='\t', header=list(header_rows))
            
            # Assign the merged header as column names
            df.columns = merged_header
            st.write("### Multiple header applied")
        elif header_option == "Merge multiple rows for header":
            num_header_rows = st.number_input(
                "Select the number of rows to merge for column headers:",
                min_value=1,
                max_value=5,
                value=1
            )
            file_obj.seek(0)
            
            # Read the file to extract the header rows for merging
            if file_extension == "csv":
                temp_df = pd.read_csv(file_obj, header=list(range(num_header_rows)))
            elif file_extension in ["xls", "xlsx"]:
                temp_df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=list(range(num_header_rows)))
            elif file_extension == "txt":
                temp_df = pd.read_csv(file_obj, delimiter='\t', header=list(range(num_header_rows)))
            
            # Merge headers with an underscore and remove leading underscores if present
            merged_header = temp_df.columns.to_frame().T.fillna("").astype(str).agg("_".join).str.strip("_")
            
            # Reset the file pointer again to read the full data with the merged header
            file_obj.seek(0)
            if file_extension == "csv":
                df = pd.read_csv(file_obj, header=list(range(num_header_rows)))
            elif file_extension in ["xls", "xlsx"]:
                df = pd.read_excel(file_obj, sheet_name=selected_sheet, header=list(range(num_header_rows)))
            elif file_extension == "txt":
                df = pd.read_csv(file_obj, delimiter='\t', header=list(range(num_header_rows)))

            # Set the merged header as the dataframe columns
            df.columns = merged_header
            st.write("### Merged multiple rows header is applied ")
        # Remove duplicate columns, keeping only the first occurrence
        df = df.loc[:, ~df.columns.duplicated()]

        st.write(f"**Shape (Rows, Columns):** {df.shape}")

        # Make a copy of the DataFrame to apply modifications
        df_modified = df.copy()
        col1, col2, col3 = st.columns([2, 2, 2])
        # Expander for renaming columns with a multiselect option
        with col1:
            with st.expander("Rename Columns"):
                selected_columns = st.multiselect("Select columns to rename:", options=df.columns)
                col_rename_dict = {}

                for col in selected_columns:
                    new_name = st.text_input(f"Rename '{col}' to:", value=col)
                    col_rename_dict[col] = new_name

                # Apply renaming only to selected columns
                if col_rename_dict:
                    df_modified = df_modified.rename(columns=col_rename_dict)

        # Expander for removing columns
        with col2:
            with st.expander("Remove Columns"):
                columns_to_remove = st.multiselect("Select columns to remove:", options=df_modified.columns)
                if columns_to_remove:
                    df_modified = df_modified.drop(columns=columns_to_remove)

        # Expander for removing rows
        with col3:
            with st.expander("Remove Rows"):
                # Select rows to remove by index
                rows_to_remove = st.multiselect("Select rows to remove by index:", options=df_modified.index.tolist())
                if rows_to_remove:
                    df_modified = df_modified.drop(index=rows_to_remove)

        # Filtering Section
        st.markdown("### Apply Filters")
        filter_scope = st.radio("Filter Scope:", ["Rows", "Columns", "No Filter"], index=2)

        # Initialize the filtered_data variable to the original DataFrame
        filtered_data = df_modified.copy()

        if filter_scope == "No Filter":
            st.write("#### No filter applied.")
        else:
            # Select the target for filtering
            if filter_scope == "Rows":
                # Provide column options for filtering
                filter_column = st.selectbox("Select a column to filter rows by:", df_modified.columns)

                # Get the unique values of the selected column
                unique_values = df_modified[filter_column].unique()
                
                # Filter options based on selected column values
                filter_value = st.selectbox("Select a value to filter by:", unique_values)

                # Equal to filter
                if st.checkbox("Apply 'Equal to' filter"):
                    filtered_data = filtered_data[filtered_data[filter_column] == filter_value]

                # Greater than or equal to filter
                if st.checkbox("Apply 'Greater than or equal to' filter"):
                    min_value = st.number_input("Enter the minimum value (for 'Greater than or equal to'):", value=0.0)
                    filtered_data = filtered_data[filtered_data[filter_column] >= min_value]

                # Less than or equal to filter
                if st.checkbox("Apply 'Less than or equal to' filter"):
                    max_value = st.number_input("Enter the maximum value (for 'Less than or equal to'):", value=0.0)
                    filtered_data = filtered_data[filtered_data[filter_column] <= max_value]

                # Greater than filter
                if st.checkbox("Apply 'Greater than' filter"):
                    greater_value = st.number_input("Enter the value (for 'Greater than'):", value=0.0)
                    filtered_data = filtered_data[filtered_data[filter_column] > greater_value]

                # Less than filter
                if st.checkbox("Apply 'Less than' filter"):
                    less_value = st.number_input("Enter the value (for 'Less than'):", value=0.0)
                    filtered_data = filtered_data[filtered_data[filter_column] < less_value]

                # Between filter
                if st.checkbox("Apply 'Between' filter"):
                    min_range = st.number_input("Enter the minimum value (for 'Between'):", value=0.0)
                    max_range = st.number_input("Enter the maximum value (for 'Between'):", value=0.0)
                    filtered_data = filtered_data[
                        (filtered_data[filter_column] >= min_range) & (filtered_data[filter_column] <= max_range)
                    ]

            else:  # Column-based filtering
                filter_column = st.selectbox("Select a column to apply filters on:", df_modified.columns)

                # Apply filters
                # Equal to filter
                if st.checkbox("Apply 'Equal to' filter"):
                    value = st.selectbox("Select a value to filter by (for 'Equal to'):", filtered_data[filter_column].unique())
                    filtered_data = filtered_data[filtered_data[filter_column] == value]

                # Greater than or equal to filter
                if st.checkbox("Apply 'Greater than or equal to' filter"):
                    min_value = st.number_input("Enter the minimum value (for 'Greater than or equal to'):", value=0.0)
                    filtered_data = filtered_data[filtered_data[filter_column] >= min_value]

                # Less than or equal to filter
                if st.checkbox("Apply 'Less than or equal to' filter"):
                    max_value = st.number_input("Enter the maximum value (for 'Less than or equal to'):", value=0.0)
                    filtered_data = filtered_data[filtered_data[filter_column] <= max_value]

                # Greater than filter
                if st.checkbox("Apply 'Greater than' filter"):
                    greater_value = st.number_input("Enter the value (for 'Greater than'):", value=0.0)
                    filtered_data = filtered_data[filtered_data[filter_column] > greater_value]

                # Less than filter
                if st.checkbox("Apply 'Less than' filter"):
                    less_value = st.number_input("Enter the value (for 'Less than'):", value=0.0)
                    filtered_data = filtered_data[filtered_data[filter_column] < less_value]

                # Between filter
                if st.checkbox("Apply 'Between' filter"):
                    min_range = st.number_input("Enter the minimum value (for 'Between'):", value=0.0)
                    max_range = st.number_input("Enter the maximum value (for 'Between'):", value=0.0)
                    filtered_data = filtered_data[
                        (filtered_data[filter_column] >= min_range) & (filtered_data[filter_column] <= max_range)
                    ]

        

        st.write("#### Filtered Data Preview")
        st.dataframe(filtered_data, height=250, use_container_width=True)

        st.write("### Additional Data Insights")

        col1, col2, col3 = st.columns([2, 2, 2])

        with col1:
            with st.expander("Descriptive Statistics"):
                st.dataframe(filtered_data.describe(), use_container_width=True)

        with col2:
            with st.expander("Column Names and Data Types"):
                st.dataframe(filtered_data.dtypes.to_frame(name="Data Type"), use_container_width=True)

        with col3:
            with st.expander("Null Values in Data"):
                st.dataframe(filtered_data.isnull().sum().to_frame(name="Null Count"), use_container_width=True)

        col1, col2, col3 = st.columns([10, 10, 10])

        filtered_data.columns = filtered_data.columns.str.strip()

        if 'Long' in filtered_data.columns and 'Lat' in filtered_data.columns:
            filtered_data['geometry'] = filtered_data.apply(lambda row: Point(row['Long'], row['Lat']), axis=1)
            geo_df = gpd.GeoDataFrame(filtered_data, geometry='geometry', crs="EPSG:4326")
            # Load boundary shapefile if needed here...

            with col1:
                if st.button("Download Filtered Data as Shapefile ⬇️", key="download_shapefile"):
                    if selected_sheet: 
                        shapefile_name = f"{base_filename}_{selected_sheet}_filtered.shp"
                    else:
                        shapefile_name = f"{base_filename}_{selected_sheet}_filtered.shp"

                    save_path = os.path.join(output_folder, shapefile_name)  # Adjust output folder as needed
                    geo_df.to_file(save_path, driver='ESRI Shapefile')
                    st.success(f"Filtered data has been saved as a shapefile: {shapefile_name}")
        else:
            st.error("Latitude and longitude columns are required to convert to a GeoDataFrame.")

        with col3:
            if st.button("Download Filtered Data as CSV file ⬇️", key="save_csv_file"):
                # Check if a sheet is selected and adjust the file name accordingly
                if selected_sheet:  # Assuming 'selected_sheet' holds the name of the selected sheet or is None
                    cleaned_file_name = f"{base_filename}_{selected_sheet}_Modified.{file_extension}"
                else:
                    cleaned_file_name = f"{base_filename}_Modified.{file_extension}"
                save_path = os.path.join(output_folder, cleaned_file_name)  # Adjust output folder as needed
                
                if file_extension == "csv":
                    filtered_data.to_csv(save_path, index=False)
                elif file_extension in ["xls", "xlsx"]:
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                        filtered_data.to_excel(writer, sheet_name="Sheet1", index=False)
                    data = output.getvalue()
                    with pd.ExcelWriter(save_path, engine="xlsxwriter") as writer:
                        filtered_data.to_excel(writer, sheet_name="Sheet1", index=False)
                elif file_extension == "txt":
                    filtered_data.to_csv(save_path, sep='\t', index=False)
                
                st.success(f"File successfully saved in the output folder: {save_path}")




    
    # Validate the folder path
    # if main_dataset_folder:
    #     if os.path.exists(main_dataset_folder):
    #         #st.success(f"Main dataset folder set to: {main_dataset_folder}")
    #     else:
    #         st.error("The folder path does not exist. Please enter a valid path.")

    # List subfolders for shapefile and TIFF selection separately
    if uploaded_files:
        subfolders = [f.name for f in Path(main_dataset_folder).iterdir() if f.is_dir()]
        plot_shp_folder = st.selectbox("Select a folder for shapefile data to merge the selected files:", subfolders, index=None, key="shp")
        if plot_shp_folder:
            shp_folder_path = os.path.join(main_dataset_folder, plot_shp_folder)
            selected_shapefile = [f.name for f in Path(shp_folder_path).rglob("*.shp")]
            plot_shp = st.selectbox("Select the shapefile:", selected_shapefile, index=None)
            plot_shp_file = next((f for f in Path(shp_folder_path).rglob("*.shp") if f.name == plot_shp), None)
            
            if uploaded_files and plot_shp:
                gdf = gpd.read_file(plot_shp_file)

                # Merge the GeoDataFrame with the DataFrame on TRT_ID and ID
                merged_gdf = gdf.merge(merged_df, left_on='TRT_ID', right_on='Farm_ID', how='left')
                
                df1_path = next((file for file in uploaded_files if file.name.endswith("VWC.xlsx")), None)
                df1 = pd.read_excel(df1_path, skiprows=2)
                df1['SMC(%)'] = df1.iloc[:, 3:].mean(axis=1)
                new_df = df1.iloc[:, list(range(3)) + [-1]]

                st.write(new_df)
                pivot_wider_df  =st.selectbox("Pivot the dataset wider on Date basis", ["Yes", "No"])

                if pivot_wider_df =="Yes":
                # Pivot to wider format
                    df_wide = new_df.pivot(index=['Plot #', 'Block #'], columns='Date', values='SMC(%)')

                    # Flatten column names and format them as "SMC(%)_<Date>"
                    df_wide.columns = [f'SMC(%)_{col}' for col in df_wide.columns]

                    # Reset index if needed
                    df_wide = df_wide.reset_index()
                    date_columns = [col for col in df_wide.columns if 'SMC(%)' in col]
                    combined_columns = []

                    for i in range(len(date_columns) - 1):
                        # Get the dates from the column names
                        date1 = pd.to_datetime(date_columns[i].split('_')[-1])
                        date2 = pd.to_datetime(date_columns[i + 1].split('_')[-1])
                        
                        # Check if dates are consecutive
                        if (date2 - date1).days == 1:
                            new_column_name = f"SMC(%)_2day_{date2.strftime('%Y-%m-%d')}"
                            df_wide[new_column_name] = df_wide[date_columns[i]].fillna(0) + df_wide[date_columns[i + 1]].fillna(0)
                            combined_columns.append(new_column_name)

                    # Drop original columns if desired
                    df_final_SMC = df_wide.drop(columns=date_columns, errors='ignore')

                    # Ensure all column names are strings
                    for column in df_final_SMC.columns:
                        if pd.api.types.is_datetime64_any_dtype(df_final_SMC[column]):
                            df_final_SMC[column] = df_final_SMC[column].dt.strftime('%Y-%m-%d')

                elif pivot_wider_df =="No":
                    df_final_SMC = new_df

                merged_gdf_1 = merged_gdf.merge(df_final_SMC, left_on="Plot_ID", right_on="Plot #", how='left')

                # Optional: Drop the original ID column from the CSV if not needed
                merged_gdf1 = merged_gdf_1.drop(columns=['Farm_ID', "Plot #", "Block #", 'ID'], errors='ignore')
                st.write(merged_gdf1)
                # Convert merged GeoDataFrame to CSV format
                merged_gdf2 = merged_gdf1.to_csv(index=False)
                
                # Provide a download button for the CSV file
                if st.button("Save merged datafile as CSV"):
                    csv_filename = "Output/Merged_data.csv"
                    output_csv_path = os.path.join(main_dataset_folder, csv_filename)
                    merged_gdf1.to_csv(output_csv_path, index=False)  # Save to output directory
                    with open(output_csv_path, 'rb') as f:
                        st.download_button("Download CSV to local directory", f, file_name=csv_filename, mime="text/csv")
                    st.success(f"Merged data has been saved as a CSV file: {csv_filename}")

elif page =='Data Interpretation':
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'> TAPS Data Interpretation Dashboard </h1>", unsafe_allow_html=True)
    st.markdown("<h5 style='text-align: center; color: #6c757d;'> Data Made Simple: Transforming Complexity into Clarity.</h3>", unsafe_allow_html=True)
    # Load the CSV and convert it to a GeoDataFrame
    csv_file_path = st.file_uploader("Upload the output .csv file", type=["csv", "xls", "xlsx", "txt"])
    

    if csv_file_path is not None:
        ndvi_dataframes = pd.read_csv(csv_file_path, delimiter=",")
        with st.expander("Data Preview"):
            st.write(ndvi_dataframes)

        df = ndvi_dataframes.copy()
        
        df['geometry'] = df['geometry'].apply(wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry='geometry')
        gdf.set_crs(epsg=4326, inplace=True)

        # Select column for Y values
        column_y = st.selectbox("Select column for polygon coloring:", gdf.columns, index = None)
        # Create a figure for the GeoDataFrame plot
        
        if column_y is not None:
            fig, ax = plt.subplots(figsize=(10, 8))
            # Plot the GeoDataFrame with a color map based on the selected column
            gdf.plot(column=column_y, ax=ax, legend=True, cmap='RdYlGn', edgecolor='black')
            ax.ticklabel_format(useOffset=False, style='plain')
            ax.set_title("GeoDataFrame with Polygon Symbology")
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.tick_params(axis='both', which= 'major', labelsize= 12)
            plt.tight_layout()

            # Create the bar plot
            average_values = gdf.groupby('TRT_ID')[column_y].mean().reset_index()
            overall_mean = average_values[column_y].mean()

         # Ensure ID is string

           # Create the bar plot
            fig_bar, ax_bar = plt.subplots(figsize=(15, 8))
            ax_bar.bar(average_values['TRT_ID'].astype(int).astype(str), average_values[column_y], color='skyblue')
            ax_bar.axhline(y=overall_mean, color='red', linestyle='--', linewidth=2.5, label=f'Mean: {overall_mean:.2f}')
            ax_bar.set_title("Average values per ID", fontsize=14)  # Change title font size here
            ax_bar.set_xlabel("ID", fontsize=12)
            ax_bar.set_ylabel(column_y, fontsize=12)

            # Change the font size of x and y tick labels
            ax_bar.tick_params(axis='both', which='major', labelsize=12, labelcolor ='black')  # Change the labelsize to your desired font size

            ax_bar.legend()

            plt.tight_layout()

            # Display the GeoDataFrame and bar plot side by side
            col1, col2 = st.columns(2)
            with col1:
                st.write("### GeoDataFrame Display")
                # Display the GeoDataFrame plot in Streamlit
                st.pyplot(fig)
                  # Save both the plot and GeoDataFrame display as an image
                img_buffer = BytesIO()
                fig.savefig(img_buffer, format='jpg')
                img_buffer.seek(0)
                
                # Download button to save both as a common JPG
                st.download_button(
                    label="Download GeoDataFrame as JPG",
                    data=img_buffer,
                    file_name="gdf_plots.jpg",
                    mime="image/jpeg"
                )
            with col2:
                st.write("### Bar Plot")
                st.pyplot(fig_bar)
                img_buffer = BytesIO()
                fig_bar.savefig(img_buffer, format='jpg')
                img_buffer.seek(0)
                
                # Download button to save both as a common JPG
                st.download_button(
                    label="Download Bar Plot as JPG",
                    data=img_buffer,
                    file_name="bar_plots.jpg",
                    mime="image/jpeg"
                )

                    # Assuming this setup is correct and files are properly loaded into 'filtered_data'
        plot_type = st.selectbox("Select the plot type:", ["None", "Scatter Plot", "Histogram", "Bar Plot", "Box Plot", "Heatmap", "Line Plot"])

        if plot_type == "Scatter Plot":
            x_axis = st.selectbox("Select the x-axis variable:", gdf.columns)
            y_axis = st.selectbox("Select the y-axis variable:", gdf.columns)
            
            if x_axis in gdf.columns and y_axis in gdf.columns:
                scatter_chart = alt.Chart(gdf).mark_circle(size=60).encode(
                    x=alt.X(x_axis, type='quantitative'),  # Specifying data type explicitly
                    y=alt.Y(y_axis, type='quantitative'),
                    tooltip=[x_axis, y_axis]
                ).interactive()
                st.altair_chart(scatter_chart, use_container_width=True)

        elif plot_type == "Histogram":
            column_to_plot = st.selectbox("Select the column for histogram:", gdf.columns)
            if column_to_plot in gdf.columns:
                histogram = alt.Chart(gdf).mark_bar().encode(
                    alt.X(column_to_plot, bin=True, type='quantitative'),  # Specifying data type explicitly
                    y='count()'
                ).interactive()
                st.altair_chart(histogram, use_container_width=True)

        elif plot_type == "Bar Plot":
            column_to_plot = st.selectbox("Select the column for bar plot:", gdf.columns)
            if column_to_plot in gdf.columns:
                bar_plot = alt.Chart(gdf).mark_bar().encode(
                    x=alt.X(column_to_plot, type='nominal'),  # Specifying data type as nominal
                    y='count()'
                ).interactive()
                st.altair_chart(bar_plot, use_container_width=True)

        elif plot_type == "Box Plot":
            column_to_plot = st.selectbox("Select the column for box plot:", gdf.columns)
            if column_to_plot in gdf.columns:
                box_plot = alt.Chart(gdf).mark_boxplot().encode(
                    x=alt.X(column_to_plot, type='nominal'),  # Nominal type for categorization
                    y=alt.Y(column_to_plot, type='quantitative')  # Quantitative type for values
                ).interactive()
                st.altair_chart(box_plot, use_container_width=True)

        elif plot_type == "Heatmap":
            x_axis = st.selectbox("Select the x-axis variable for heatmap:", gdf.columns)
            y_axis = st.selectbox("Select the y-axis variable for heatmap:", gdf.columns)
            if x_axis in gdf.columns and y_axis in gdf.columns:
                heatmap = alt.Chart(gdf).mark_rect().encode(
                    x=alt.X(x_axis, type='nominal'),  # Using nominal for category-like data
                    y=alt.Y(y_axis, type='nominal'),
                    color='count()'  # Default quantitative count for heatmap intensity
                ).interactive()
                st.altair_chart(heatmap, use_container_width=True)

        elif plot_type == "Line Plot":
            x_axis = st.selectbox("Select the x-axis variable for line plot:", gdf.columns)
            y_axis = st.selectbox("Select the y-axis variable for line plot:", gdf.columns)
            if x_axis in gdf.columns and y_axis in gdf.columns:
                line_chart = alt.Chart(gdf).mark_line().encode(
                    x=alt.X(x_axis, type='temporal' if 'date' in x_axis.lower() else 'quantitative'),  # Temporal for dates, else quantitative
                    y=alt.Y(y_axis, type='quantitative'),
                    tooltip=[x_axis, y_axis]
                ).interactive()
                st.altair_chart(line_chart, use_container_width=True)
        # cont1 = st.container()
        
        # with cont1:
        #     st.subheader("Analyze 2024_TAPS_management.xlsx or upload your own", divider="blue")
        #     uploaded_file = st.file_uploader("Upload an Excel or CSVfile", type=["xlsx", "csv"])

        #     if uploaded_file is not None:
        #         if uploaded_file.name.endswith(".xlsx") or uploaded_file.name.endswith(".xls"):
        #             use_uploaded_file = True
        #             ndvi_dataframes_uploaded = pd.read_excel(uploaded_file)
        #         elif uploaded_file.name.endswith(".csv"):
        #             use_uploaded_file = True
        #             ndvi_dataframes_uploaded = pd.read_csv(uploaded_file)
        #         else:
        #             use_uploaded_file = False
        #             st.error("Invalid file format. Please upload an Excel or CSV file. \nSupported formats: .xlsx, .xls, .csv: \ndefaulting to ./Datasets/Management/2024_TAPS_management.xlsx")          
        #     else:
        #         st.write("No file uploaded. \nUsing default ./Datasets/Management/2024_TAPS_management.xlsx")
        #         use_uploaded_file = False
                
        
        # setup column 2 in streamlit
        # with di_col2:
                

        # setup column 3 in streamlit
        use_uploaded_file =False
        cont2 = st.container()
        with cont2:
            cont2_col1, cont2_col2 = st.columns([0.2, 0.8])
            with cont2_col1:
                st.subheader("Plot options", divider="green")
                
                # select a graph type
                selected_graph_type = st.radio("Select a graph type", ["Bar", "Scatter"])
                
                st.subheader("NDVI & MCARI2 Analysis", divider="green")
                
                checkbox_options = ["NDVI", "MCARI2", "Irrigation", "Fertilizer"]
                selected_option = st.radio("Select an option", checkbox_options)
                # st.session_state
                    
                # if use_uploaded_file:
                #     if selected_option == "NDVI":
                #         dates_strings = [col.split("_")[-1] for col in ndvi_dataframes_uploaded.columns if col.startswith("mean_NDVI")]
                #         dates = pd.to_datetime(dates_strings) 
                #     else:
                #         dates_strings = [col.split("_")[-1] for col in ndvi_dataframes_uploaded.columns if col.startswith("mean_MCARI2")]
                #         dates = pd.to_datetime(dates_strings)
                # else:
                if selected_option == "NDVI":
                    dates_strings = [col.split("_")[-1] for col in ndvi_dataframes.columns if col.startswith("mean_NDVI")]
                    dates = pd.to_datetime(dates_strings)
                else:
                    dates_strings = [col.split("_")[-1] for col in ndvi_dataframes.columns if col.startswith("mean_MCARI2")]
                    dates = pd.to_datetime(dates_strings)
                    
                # Manage state with st.session_state
                if 'selected_date' not in st.session_state:
                    st.session_state['selected_date'] = dates[0]
                        
                if selected_option == "Irrigation":
                    # filter dataframe based on selected date
                    filtered_columns = []
                    for col in irr_df.columns:
                        if col.startswith('Irrigation (inches)'):
                            if is_date(col.split('_')[1]):
                                if pd.to_datetime(col.split('_')[1]) <= st.session_state['selected_date']:
                                    filtered_columns.append(col)
                                    
                    # Summing the values
                    plot_sums = irr_df[filtered_columns].sum(axis=1)

                    # Converting to a DataFrame
                    plot_sums_df = pd.DataFrame(plot_sums, columns=['Irrigation'])

                    # Adding the Plot ID as a column
                    plot_sums_df['TRT_ID'] = irr_df['ID']

                    # Reordering columns to have Plot ID first
                    plot_sums_df = plot_sums_df[['TRT_ID', 'Irrigation']]
                    
                else:
                    
                    # filter dataframe based on selected date
                    filtered_columns = []
                    for col in nfert_df.columns:
                        if col.startswith('Nitrogen'):
                            if is_date(col.split('_')[2]):
                                if pd.to_datetime(col.split('_')[2]) <= st.session_state['selected_date']:
                                    filtered_columns.append(col)
                            elif col.split('_')[2] == 'Variable':
                                filtered_columns.append(col)
                    
                    # Summing the values
                    nfert_df[filtered_columns] = nfert_df[filtered_columns].apply(pd.to_numeric, errors='coerce')
                    plot_sums = nfert_df[filtered_columns].sum(axis=1)

                    # Converting to a DataFrame
                    plot_sums_df = pd.DataFrame(plot_sums, columns=['Fertilizer'])

                    # Adding the Plot ID as a column
                    plot_sums_df['TRT_ID'] = nfert_df['ID']

                    # Reordering columns to have Plot ID first
                    plot_sums_df = plot_sums_df[['TRT_ID', 'Fertilizer']]
                                                
                # select a date
                # selected_date_selectbox = st.selectbox("Select a date", dates, index=dates.get_loc(st.session_state['selected_date']))
                # st.session_state['selected_date'] = selected_date_selectbox
                selected_date_selectbox = st.session_state['selected_date']
                selected_date_str = selected_date_selectbox.strftime("%Y-%m-%d")
                st.session_state['selected_date_str'] = selected_date_str
                
                # select a date using a slider                    
                slider_date = st.select_slider(
                    "Select Date",
                    options=dates,
                    value=st.session_state['selected_date'],
                ) 
                slider_date_str = slider_date.strftime("%Y-%m-%d") 
                st.session_state['selected_date'] = slider_date
                st.session_state['selected_date_str'] = slider_date_str                                        
                    
                
            with cont2_col2:
                
                st.subheader("NDVI or MCARI2 Plots", divider="green")                                    
                    
                if selected_graph_type == "Bar":
                    st.write(f"{selected_option} by TRT_ID for {st.session_state['selected_date'].strftime('%Y-%m-%d')}")
                    ndvi_sum = ndvi_dataframes.groupby('TRT_ID')[f'mean_NDVI_{st.session_state["selected_date_str"]}'].mean()
                    
                    plot_data = pd.DataFrame({
                        # "NDVI": ndvi_sum,
                        f"{selected_option}": set_plot_dataframe(selected_option),
                        "TRT_ID": plot_sums_df['TRT_ID']
                    })
                    fig = px.bar(plot_data, 
                                    x="TRT_ID",
                                    y=set_axis_function(selected_option),
                                    color=set_axis_function(selected_option),
                                    hover_data=["TRT_ID"])
                    fig.update_layout(xaxis_title="TRT_ID",
                                        yaxis_title=set_title_function(selected_option)
                                        )
                    st.plotly_chart(fig)
                                                        
                elif selected_graph_type == "Scatter":
                    st.write(f"{selected_option} vs Irrigation values for {st.session_state['selected_date'].strftime('%Y-%m-%d')}")
                    ndvi_sum = ndvi_dataframes.groupby('TRT_ID')[f'mean_NDVI_{st.session_state["selected_date_str"]}'].mean()
                    
                    plot_data = pd.DataFrame({
                        f"{selected_option}": set_plot_dataframe(selected_option),
                        "TRT_ID": plot_sums_df['TRT_ID']
                    })
                    fig = px.scatter(plot_data, 
                                        x="TRT_ID",
                                        y=set_axis_function(selected_option),
                                        color=set_axis_function(selected_option),
                                        hover_data=["TRT_ID"]
                                        )
                    fig.update_layout(xaxis_title="TRT_ID",
                                        yaxis_title=set_title_function(selected_option)
                                        )
                    st.plotly_chart(fig)
                
    try:           
        if slider_date != selected_date_selectbox:
            selected_date_selectbox = slider_date
            st.rerun()
        if selected_date_str != slider_date_str:
            selected_date_str = slider_date_str
            st.rerun()
                    
        if st.session_state['selected_date'] != selected_date_selectbox:
            st.session_state['selected_date'] = selected_date_selectbox
            st.rerun()
        if st.session_state['selected_date_str'] != selected_date_str:
            st.session_state['selected_date_str'] = selected_date_str
            st.rerun()

    except Exception as e:
        print(f"Error: {str(e)}")

                    
                
                
        

