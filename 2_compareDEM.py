import configparser
import csv
import json
import os
import sys
import re
import warnings
import Metashape
import numpy as np
import pandas as pd
import rasterio as rio
import rioxarray
import matplotlib.pyplot as plt
from metashape_util.dialog import Dialog
from metashape_util.file_utils import FileUtils
from metashape_util.geo_utils import GeoUtils
from metashape_util.chunk import ChunkUtils

app = Metashape.Application()
doc = app.document
dialog = Dialog(app)

#config parser
config = configparser.ConfigParser()
config.read(sys.path[0] + "\config.ini")

documentFile = FileUtils.parsePath(doc.path)

# CONFIG
DEM_EXPORT_FOLDER = os.path.expanduser(config["Defaults"].get("DEM_EXPORT_FOLDER", "~\\Desktop\\autoDEM\\"))
DEM_EXPORT_FOLDER += documentFile['name'] + "\\"


# Read csv file
# Format: !!! First line is ignored (header line)
# Betrieb;       Versuchsfläche;     Bezeichnung Messpunkt/Dateiname;    Type;   Longitude;  Latitude;       Altitude
# Meiereihof;    R3/1;               R3/1 - GCP Nordost;                 GCP;    9,21929980; 48,71619670;    364,70
geocoord_csv_files = dict(config["GEOCOORD_FILES"].items())

# Constant var containing all parcel positions
FIELD_PARCELS = FileUtils.read_geocoord_files(geocoord_csv_files)

if not FIELD_PARCELS: # if dictionary is empty raise exception and terminate
    raise Exception("Error: No Geocoord files found. Check config.ini: Section [GEOCOORD_FILES] should have at least one key with working file path")

# Check for avaliable exported tif files (the DEM files)
# Also scan folder for task files (containing task in name)
dem_files = []
task_csv_files = {}
for entry in os.scandir(DEM_EXPORT_FOLDER):
    file = FileUtils.parsePath(entry.path)
    if(file["extension"].upper() in [".TIF"]): # only scan for .tif files
        dem_files.append(file["name"])
    if(re.search(r"[\_\.]task[\_\.]|\Atask[\_\.]", file["filename"], re.IGNORECASE) and file["extension"].upper() in [".CSV"]):
        # add to task csv files
        task_csv_files[file["name"]] = entry.path



# Sort dem files by name ( = date asc)
dem_files.sort()

# the taks file contains any task data, which parcels shold be compared against which
# if no such file in the folder the next function creates a new task file
# the file format (CSV) should match following template:
# Bezeichnung;  Basismodell;    Aufzeichnung;   Parzelle;   Index N;    Index O;    Geo Koordinaten
# BM1PA;        2022-03-23_R1;  2022-03-29_R1;  A;          0;          0;          aufwuchs1



createTaskFile = len(task_csv_files.keys()) <= 0 or app.getBool("Soll ein neuer Auftrag angelegt werden?") == True

if(createTaskFile):
    if len(task_csv_files.keys()) <= 0:
        app.messageBox("Es existiert noch keine Auftrags Datei. \n Die Auftragsdatei enhält Informationen welche Parzellen verglichen werden sollen. \n im nächsten Schritt wird eine neue Auftragsdatei erstellt")

    taskFileId = app.getString("Geben sie dem Auftrag einen Namen. Gibt es nur einen Auftrag so kann das Feld leer gelassen werden.")
    print(taskFileId)
    if(taskFileId != None):
        # First step is to determine the filename of the task file
        field_date, field_name = ChunkUtils.parseChunkName(app.document.chunk.label)

        newTaskFileName = "task_" + FileUtils.name_escape(field_name) + "_" + FileUtils.name_escape(field_date[:4])
        # Add name suffix if defined
        if(taskFileId != ""):
            newTaskFileName += "_" + FileUtils.name_escape(taskFileId)
        newTaskFileName += ".csv"
        newTaskFilePath = DEM_EXPORT_FOLDER + newTaskFileName

        print("Creating new task file: " + newTaskFileName)
        if(os.path.exists(newTaskFilePath)):
            if(not app.getBool("Die Datei {} exsitiert bereits, soll sie überschrieben werden?".format(newTaskFilePath))):
                raise Exception("Exited")

        # Select Base models
        baseModelCount = max(1, app.getInt("Wieviele verschiedene Basismodelle sollen verwendet werden?", 1))
        baseModelList = []
        for b in range(0, baseModelCount):
            availiable_dem_files = [d for d in dem_files if d not in baseModelList]
            baseModel = dialog.getListCoice(dem_files, "({} / {}) \n\n Wähle Basis-Modell (die Null-Referenz). Damit werden alle anderen Messungen verglichen".format(b+1, baseModelCount))
            print("Setting {} as Base Model {}".format(baseModel, b+1))
            baseModelList.append(baseModel)
        baseModelList.sort()
        
        with open(newTaskFilePath, "w", newline='') as csv_file:
            writer = csv.writer(csv_file, delimiter=";")
            writer.writerow(["Bezeichnung", "Basismodell", "Aufzeichnung", "Parzelle", "Index N", "Index O", "Geo Koordinaten", "Rasterlaenge NS", "Rasterlaenge OW", "Raster Ursprung"])

            rec = 0 # record number
            parcelNo = 0
            base_model_index = 0
            geocoord_file_index = 0
            currentBaseModel = baseModelList[0]
            for dem_file in dem_files:
                # Loop through all exported tif files
                # if current file is the base model
                def checkIfBaseModel():
                    global rec, currentBaseModel, parcelNo, base_model_index, geocoord_file_index
                    for bm in baseModelList:
                        if(bm == dem_file):
                            if(currentBaseModel != bm):
                                currentBaseModel = bm

                            if rec != 0: # if first record is the base model dont increment the geocoord file
                                geocoord_file_index += 1
                                geocoord_file_index = min(geocoord_file_index, len(FIELD_PARCELS.keys()) - 1) # ensure there is a geocoord file with this key
                            parcelNo = 0 # reset parcel number - after base model we restart at parcel 0
                            return True
                    return False
                if(checkIfBaseModel()):
                    continue
                
                rec += 1 
                geocoord_file_key = list(FIELD_PARCELS.keys())[geocoord_file_index]
                

                for parcel in FIELD_PARCELS[geocoord_file_key][field_name]:
                    if(parcel in ["GCP", "BS"]): continue
                    bmNo = rec
                    bez = "BM{}P{}{}".format(bmNo, parcel, parcelNo+1)

                    writer.writerow([bez, currentBaseModel, dem_file, parcel, parcelNo, 0, geocoord_file_key, 1, 1, "SW"])

                parcelNo += 1

        raise Exception("Bitte fülle die Auftragsdatei \"{}\" mit den gewünschten Operationen und starte dieses Skript neu.".format(newTaskFileName))
    raise Exception("Exited Program")

print(task_csv_files)
if(len(list(task_csv_files.keys())) > 1):
    task_name = dialog.getListCoice(list(task_csv_files.keys()), "Es wurden mehrere Auftragsdateien gefunden. \n Welche soll verarbeitet werden?")
    task_csv_file = task_csv_files[task_name]
else:
    # if only one task file exists take that
    task_csv_file = task_csv_files[list(task_csv_files.keys())[0]]

# Determine name of result folder
taskFile = FileUtils.parsePath(task_csv_file)
resultFolderName = re.sub(r"[\_]task[\_]|\Atask[\_]|[\_]task\Z" , "", taskFile["name"])

# First create the export folders if they are not already there
# All results of one calculation are stored in one sub directory
RESULT_FOLDER = DEM_EXPORT_FOLDER + resultFolderName + "\\"
FileUtils.createDirsIfNotExists(RESULT_FOLDER + "input\\")
FileUtils.createDirsIfNotExists(RESULT_FOLDER + "difference\\")

# Start executing calculations

# Read tasks file
tasks_df = pd.read_csv(task_csv_file, index_col='Bezeichnung', delimiter=";", decimal=",")

# This is the export csv file
task_csv_file_out = RESULT_FOLDER + resultFolderName + ".csv"

# Create a basic object containing all parcel tile coordinates
parcel_geojson = {"type": "FeatureCollection", "features": []}
parcel_geojson_path = RESULT_FOLDER + resultFolderName + ".geojson"


# Loop through tasks and calculate result
for index, task in tasks_df.iterrows():
    print("Calculating Tile {}...".format(index))

    base_model_path = DEM_EXPORT_FOLDER + task["Basismodell"] + ".tif"
    compare_model_path = DEM_EXPORT_FOLDER + task["Aufzeichnung"] + ".tif"

    # Geo coord file falls back to first if not defined
    geo_coord_file = task["Geo Koordinaten"] or list(FIELD_PARCELS.keys())[0]

    if geo_coord_file in FIELD_PARCELS:
        # Try to get path from config file
        field_parcel_data = FIELD_PARCELS[geo_coord_file]
    elif os.path.exists(geo_coord_file):
        # Also allow path specified in task file
        field_parcel_data = FileUtils.read_geocoord_file(geo_coord_file)
    else:
        raise Exception("Geocoord file not found: {} Please check in config.ini or specify absolute path in compare_dem_task.csv file".format(geo_coord_file))

    # get the field name from the first chunk label
    field_date, field_name = ChunkUtils.parseChunkName(doc.chunks[0].label)
    
    # get raw parcel corner data
    parcel_full_u = field_parcel_data[field_name][task["Parzelle"]]

    # parcel tile with
    parcel_width_y = task.get("Rasterlaenge NS", False) or 1
    parcel_width_x = task.get("Rasterlaenge OW", False) or 1

    # parcel tile origin (the corner of the parcel which is considered as fix point for the raster)
    parcel_origin = task.get("Raster Ursprung", False) or "SW"

    # Sort parcel corners to ensure right orientation.
    # Order is SO, SW, NW, NO
    parcel_full = GeoUtils.toNumpy(  GeoUtils.orderRectPoints(parcel_full_u)  )

    # Cut the tile from the full parcel. Tile dimensions are 1 by 1 meters by default.
    # Index N and Index O starting from 0 and increment in directions north and east
    parcel_tile = GeoUtils.getParcelTile(parcel_full, 
                                         x_index = task["Index N"], 
                                         y_index = task["Index O"], 
                                         tile_mode = GeoUtils.TILE_MODE_PARALLEL, 
                                         tile_size_x_m = parcel_width_x,
                                         tile_size_y_m = parcel_width_y,
                                         tile_origin = parcel_origin)

    mask_parcel = {'type': 'Polygon', 'coordinates': [parcel_tile]}

    try:
        # Read the tif files with rasterio an clip directly to parcel tile to save ressources
        with rio.open(base_model_path) as src, rio.vrt.WarpedVRT(src) as vrt:
            base_dem = rioxarray.open_rasterio(vrt, masked=True).rio.clip(
                geometries=[mask_parcel],
                all_touched=True,
                from_disk=True,
            ).squeeze()

        with rio.open(compare_model_path) as src, rio.vrt.WarpedVRT(src) as vrt:
            compare_dem = rioxarray.open_rasterio(vrt, masked=True).rio.clip(
                geometries=[mask_parcel],
                all_touched=True,
                from_disk=True,
            ).squeeze()
    except ValueError:
        warnings.warn("{} Intersection is empty: Parcel does not overlap DEM.".format(index))
        print("Possible solution: Check column order in geocoord file: [Betrieb, Versuchsfläche, Bezeichung, Type, Lon, Lat, Alt]")
        print("GeoCoordFile: {}".format(geo_coord_file))
        print("Parcel Corners: {}".format(parcel_tile))
        continue

    # Reproject match ensures the tiles of both datasets are same dimensions 
    # (due inconstant elevation model dimensions the pixels in the tiles slightly differ from each other)
    repr_compare = compare_dem.rio.reproject_match(base_dem)

    # Subtract raster datasets from each other
    dem_diff = repr_compare - base_dem

    # Export raster file for debugging:
    base_dem.rio.to_raster(RESULT_FOLDER + "input\\" + index + "_base.tif")
    repr_compare.rio.to_raster(RESULT_FOLDER + "input\\" + index + "_compare.tif")
    dem_diff.rio.to_raster(RESULT_FOLDER + "difference\\" + index + ".tif")


    # save results to results csv
    def saveVal(col, val):
        print("{}: \t\t {}".format(col,val))
        tasks_df.loc[index, col] = str(val).replace(".", ",")

    saveVal("Mean", dem_diff.mean().item())
    saveVal("Std", dem_diff.std().item())
    saveVal("Min", dem_diff.min().item())
    saveVal("Max", dem_diff.max().item())
    saveVal("Q25", dem_diff.quantile(0.25).item())
    saveVal("Q50", dem_diff.median().item())
    saveVal("Q75", dem_diff.quantile(0.75).item())

    # add the mask area (the parcel tile) to geojson feature collection
    parcel_geojson["features"].append({
        "type": "Feature",
        "geometry": mask_parcel,
        "properties": {
          "name": index,
          "field": field_name,
          "index-n": task["Index N"],
          "index-o": task["Index O"],
          "mean": dem_diff.mean().item(),
          "std": dem_diff.std().item(),
          "min": dem_diff.min().item(),
          "max": dem_diff.max().item(),
          "Q25": dem_diff.quantile(0.25).item(),
          "Q50": dem_diff.median().item(),
          "Q75": dem_diff.quantile(0.75).item()
        }
      })

    app.update()

# Class Np encoder handles numpy arrays in json export
class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)
# export geojson file
with open(parcel_geojson_path, 'w', encoding='utf8') as pf:
    json.dump(parcel_geojson, pf, indent=4, cls=NpEncoder)
    print("The probed area dimensions where exported to {}".format(parcel_geojson_path))

print("================================")
print("Finished task. Check {} for results.".format(task_csv_file_out))
print("================================")
# write result to result csv
tasks_df.to_csv(task_csv_file_out, sep=";", decimal=",")