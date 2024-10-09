import tkinter as tk
from tkinter import filedialog, messagebox, Toplevel, Text, Scrollbar
from tkinter import ttk
import pandas as pd
from sklearn.cluster import KMeans
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
import webbrowser
from geopy.geocoders import Nominatim
import time
import openrouteservice as ors
import creds
import threading

# Main function to load data, perform clustering, and return results
def process_geojson(file_path, n_clusters):
    gdf = gpd.read_file(file_path)
    if 'geometry' not in gdf.columns:
        raise ValueError("The provided GeoJSON file does not contain a 'geometry' column.")
    if not gdf.geometry.is_valid.all():
        gdf = gdf.set_geometry(gdf.geometry.buffer(0))
    if gdf.crs is None or gdf.crs.is_geographic:
        gdf = gdf.to_crs(epsg=4326)
    gdf['x'] = gdf.geometry.x
    gdf['y'] = gdf.geometry.y
    kmeans = KMeans(n_clusters=n_clusters, n_init=10)
    gdf['cluster'] = kmeans.fit_predict(gdf[['x', 'y']])

    # Reverse Geocoding to get place names
    geolocator = Nominatim(user_agent="fire_density_app")
    gdf['place_name'] = gdf.apply(lambda row: get_place_name(geolocator, row['y'], row['x']), axis=1)

    # Add custom group labels
    gdf['group'] = gdf['cluster'].apply(lambda x: f"Group {x + 1}")
    return gdf

# Helper function for reverse geocoding
def get_place_name(geolocator, lat, lon):
    try:
        location = geolocator.reverse((lat, lon), timeout=10)
        return location.address if location else "Unknown"
    except Exception as e:
        print(f"Geocoding error: {e}")
        return "Unknown"

# GUI Class
class FireDensityApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fire Density Analysis Tool")
        self.root.geometry("800x600")
        self.root.configure(bg="#e0e0e0")  # Light gray background

        # Set the application icon
        self.root.iconbitmap(r"C:\Users\hp\Downloads\Fire-Vehicle-Distribution--master\Fire-Vehicle-Distribution--master\icon\medical-27_icon-icons.com_73934.ico")

        # Styling
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Helvetica', 10), padding=10, relief="flat", background="#007acc", foreground="#ffffff")
        style.configure('TLabel', font=('Helvetica', 11), padding=5, background="#e0e0e0")
        style.configure('TEntry', font=('Helvetica', 11), padding=5)
        style.configure('TRadiobutton', font=('Helvetica', 11), padding=5)

        # Main Frame for File Upload and Clustering Section
        self.main_frame = ttk.Frame(root, padding=20)
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure the root window and main frame for centralization
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

        # First Section: File Upload and Number of Clusters Input
        self.file_label = ttk.Label(self.main_frame, text="Choose a GeoJSON file:")
        self.file_label.grid(row=0, column=0, padx=10, pady=10, sticky="e")

        self.upload_button = ttk.Button(self.main_frame, text="Upload", command=self.upload_file)
        self.upload_button.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.cluster_label = ttk.Label(self.main_frame, text="Enter number of firefighting vehicles:")
        self.cluster_label.grid(row=1, column=0, padx=10, pady=10, sticky="e")

        self.cluster_entry = ttk.Entry(self.main_frame)
        self.cluster_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.process_button = ttk.Button(self.main_frame, text="Process", command=self.process_data)
        self.process_button.grid(row=2, column=0, columnspan=2, pady=20, sticky="ew")

        # Second Section: Choose Output Display (Initially Hidden)
        self.display_var = tk.StringVar(value="DataFrame")
        
        self.option_label = ttk.Label(self.main_frame, text="Choose output display:")
        self.df_option = ttk.Radiobutton(self.main_frame, text="DataFrame", variable=self.display_var, value="DataFrame")
        self.map_option = ttk.Radiobutton(self.main_frame, text="Map", variable=self.display_var, value="Map")
        self.show_button = ttk.Button(self.main_frame, text="Show", command=self.display_results)

        # Instance Variables
        self.file_path = None
        self.geo_data = None

        # Initially Hide Display Options
        self.hide_display_options()


    # File upload handler
    def upload_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("GeoJSON files", "*.geojson")])
        if self.file_path:
            messagebox.showinfo("File Selected", "File loaded successfully.")

    def hide_display_options(self):
        self.option_label.grid_remove()
        self.df_option.grid_remove()
        self.map_option.grid_remove()
        self.show_button.grid_remove()

    # Data processing handler
    def process_data(self):
        if not self.file_path or not self.cluster_entry.get():
            messagebox.showerror("Input Error", "Please upload a file and enter a number of clusters.")
            return
        try:
            n_clusters = int(self.cluster_entry.get())
            self.geo_data = process_geojson(self.file_path, n_clusters)
            messagebox.showinfo("Processing Complete", "Clustering complete. Choose output display.")
            self.show_output_options()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    # Show output options
    def show_output_options(self):
        self.option_label.grid(row=3, column=0, columnspan=2, pady=10, sticky="ew")
        self.df_option.grid(row=4, column=0, padx=10, sticky="w")
        self.map_option.grid(row=4, column=1, padx=10, sticky="e")
        self.show_button.grid(row=5, column=0, columnspan=2, pady=20, sticky="ew")

    # Display results handler
    def display_results(self):
        if self.display_var.get() == "DataFrame":
            self.display_dataframe()
        elif self.display_var.get() == "Map":
            self.display_map_selection()

    # Add this method inside the FireDensityApp class
    def show_group_data(self, selected_group):
        if self.geo_data is not None:
            group_data = self.geo_data[self.geo_data['group'] == selected_group]
            display_data = group_data[['cluster', 'place_name']].reset_index()

            data_window = Toplevel(self.root)
            data_window.title(f"Details for {selected_group}")

            text_widget = Text(data_window, wrap="none", width=100, height=30)
            scrollbar = Scrollbar(data_window, orient="vertical", command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            text_widget.pack(side="left", fill="both", expand=True)

            text_widget.insert("end", display_data.to_string(index=False))

    def display_dataframe(self):
        if self.geo_data is not None:
            groups = self.geo_data['group'].unique()
            group_window = Toplevel(self.root)
            group_window.title("Select a Group to View Details")

            for group in groups:
                group_name = f"Group {group[-1]}"
                button = ttk.Button(group_window, text=group_name, command=lambda g=group: self.show_group_data(g))
                button.pack(side="left", padx=5, pady=5)

    def display_map_selection(self):
        if self.geo_data is not None:
            groups = self.geo_data['group'].unique()
            group_window = Toplevel(self.root)
            group_window.title("Select a Group to Display on Map")

            for group in groups:
                button = ttk.Button(group_window, text=group, command=lambda g=group: self.display_map(g))
                button.pack(side="left", padx=5, pady=5)

    client = ors.Client(key=creds.API_KEY)

    def display_map(self, selected_group):
        if self.geo_data is not None:
            filtered_data = self.geo_data[self.geo_data['group'] == selected_group]
            centroids = filtered_data.groupby('cluster').agg({'y': 'mean', 'x': 'mean'}).reset_index()
            centroids['place_name'] = "Fire Department Vehicle"
            
            center_lat = filtered_data.geometry.y.mean()
            center_lon = filtered_data.geometry.x.mean()
            map_ = folium.Map(location=[center_lat, center_lon], zoom_start=10)
            marker_cluster = MarkerCluster().add_to(map_)
            
            colors = ['blue', 'red', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen']
            
            for idx, (_, row) in enumerate(filtered_data.iterrows()):
                folium.Marker(
                    location=[row['y'], row['x']],
                    popup=f"{row['place_name']} - {row['group']}"
                ).add_to(marker_cluster)
                
                centroid = centroids[centroids['cluster'] == row['cluster']]
                if not centroid.empty:
                    start = [row['x'], row['y']]
                    end = [centroid['x'].values[0], centroid['y'].values[0]]
                    color = colors[idx % len(colors)]  # Cycle through the list of colors
                    self.display_route(map_, start, end, color)
                    
            for _, row in centroids.iterrows():
                folium.Marker(
                    location=[row['y'], row['x']],
                    popup=f"Fire Department Vehicle (Group {selected_group})",
                    icon=folium.Icon(color='red')
                ).add_to(marker_cluster)
            
            map_file = "cluster_map.html"
            map_.save(map_file)
            webbrowser.open(map_file)

    # Display route between two coordinates
    def display_route(self, map_, start, end, color):
        try:
            coords = [start, end]
            route = self.client.directions(coordinates=coords, profile='driving-car', format='geojson')
            folium.PolyLine(
                locations=[list(reversed(coord)) for coord in route['features'][0]['geometry']['coordinates']],
                color=color
            ).add_to(map_)
        except Exception as e:
            print(f"Error fetching route: {e}")

# Main Application Run
if __name__ == "__main__":
    root = tk.Tk()
    app = FireDensityApp(root)
    root.mainloop()