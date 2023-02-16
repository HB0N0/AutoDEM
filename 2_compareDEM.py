import configparser
import csv
import json
import os
import sys
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
dem_files = []
for entry in os.scandir(DEM_EXPORT_FOLDER):
    file = FileUtils.parsePath(entry.path)
    if(file["extension"].upper() in [".TIF"]): # only scan for .tif files
        dem_files.append(file["name"])

# this file contains any task data, which parcels shold be read
task_csv_file = DEM_EXPORT_FOLDER + "compare_dem_task.CSV"
# Bezeichnung;  Basismodell;    Aufzeichnung;   Parzelle;   Index N;    Index O;    Geo Koordinaten
# BM1PA;        2022-03-23_R1;  2022-03-29_R1;  A;          0;          0;          aufwuchs1

# the calculations results will be stored in this file. Format is the same as the tasks csv file
task_csv_file_out = DEM_EXPORT_FOLDER + "compare_dem_result.CSV"

if not os.path.exists(task_csv_file):
    createTaskFile = app.getBool("Es existiert noch keine Auftrags Datei. Die Auftragsdatei enhält Informationen welche Parzellen verglichen werden sollen. Soll eine neue Auftragsvorlage aus dem Projekt generiert werden?")
    
    if(createTaskFile):
        print("Creating Task file: " + task_csv_file)

        baseModel = dialog.getListCoice(dem_files, "Wähle das Basis-Modell (die Null-Referenz). Damit werden alle anderen Messungen verglichen")
        print("Setting {} as Base Model".format(baseModel))
        with open(task_csv_file, "w", newline='') as csv_file:
            writer = csv.writer(csv_file, delimiter=";")
            writer.writerow(["Bezeichnung", "Basismodell", "Aufzeichnung", "Parzelle", "Index N", "Index O", "Geo Koordinaten"])

            rec = 0 # record number
            parcelNo = 0
            geocoord_file_index = 0
            for dem_file in dem_files:
                # Loop through all exported tif files
                # if current file is the base model
                if dem_file == baseModel:
                    if rec != 0: # if first record is the base model dont increment the geocoord file
                        geocoord_file_index += 1
                        geocoord_file_index = min(geocoord_file_index, len(FIELD_PARCELS.keys()) - 1) # ensure there is a geocoord file with this key

                    parcelNo = 0 # reset parcel number - after base model we restart at parcel 0
                    continue
                
                rec += 1 
                geocoord_file_key = list(FIELD_PARCELS.keys())[geocoord_file_index]
                field_date, field_name = ChunkUtils.parseChunkName(dem_file)

                for parcel in FIELD_PARCELS[geocoord_file_key][field_name]:
                    if(parcel in ["GCP", "BS"]): continue

                    bez = "BM{}P{}{}".format(rec, parcel, parcelNo+1)

                    writer.writerow([bez, baseModel, dem_file, parcel, parcelNo, 0, geocoord_file_key])

                parcelNo += 1

        raise Exception("Bitte fülle die Auftragsdatei \"compare_dem_task.csv\" mit den gewünschten Operationen und starte dieses Skript neu.")


# First create the export folders if they are not already there
FileUtils.createDirsIfNotExists(DEM_EXPORT_FOLDER + "parcels\\input\\")
FileUtils.createDirsIfNotExists(DEM_EXPORT_FOLDER + "parcels\\difference\\")


# Read tasks file
tasks_df = pd.read_csv(task_csv_file, index_col='Bezeichnung', delimiter=";", decimal=",")

# Create a basic object containing all parcel tile coordinates
parcel_geojson = {"type": "FeatureCollection", "features": []}
parcel_geojson_path = DEM_EXPORT_FOLDER + "parcels\\parcel_tiles.geojson"


# Loop through tasks and calculate result
for index, task in tasks_df.iterrows():
    print("Calculating Tile {}...".format(index))

    base_model_path = DEM_EXPORT_FOLDER + task["Basismodell"] + ".tif"
    compare_model_path = DEM_EXPORT_FOLDER + task["Aufzeichnung"] + ".tif"

    # Geo coord file falls back to first if not defined
    geo_coord_file = task["Geo Koordinaten"] or list(FIELD_PARCELS.keys())[0]

    if geo_coord_file in FIELD_PARCELS:
        field_parcel_data = FIELD_PARCELS[geo_coord_file]
    elif os.path.exists(geo_coord_file):
        field_parcel_data = FileUtils.read_geocoord_file(geo_coord_file)
    else:
        raise Exception("Geocoord file not found: {} Please check in config.ini or specify absolute path in compare_dem_task.csv file".format(geo_coord_file))

    # get the field name from the first chunk label
    field_date, field_name = ChunkUtils.parseChunkName(doc.chunks[0].label)
    
    # get raw parcel corner data
    parcel_full_u = field_parcel_data[field_name][task["Parzelle"]]

    # Sort parcel corners to ensure right orientation.
    # Order is SO, SW, NW, NO
    parcel_full = GeoUtils.toNumpy(  GeoUtils.orderRectPoints(parcel_full_u)  )

    # Cut the tile from the full parcel. Tile dimensions are 1 by 1 meters by default.
    # Index N and Index O starting from 0 and increment in directions north and east
    parcel_tile = GeoUtils.getParcelTile(parcel_full, task["Index N"], task["Index O"])


    mask_parcel = {'type': 'Polygon', 'coordinates': [parcel_tile]}

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

    # Reproject match ensures the tiles of both datasets are same dimensions 
    # (due inconstant elevation model dimensions the pixels in the tiles slightly differ from each other)
    repr_compare = compare_dem.rio.reproject_match(base_dem)

    # Subtract raster datasets from each other
    dem_diff = repr_compare - base_dem

    # Export raster file for debugging:
    base_dem.rio.to_raster(DEM_EXPORT_FOLDER + "parcels\\input\\" + index + "_base.tif")
    repr_compare.rio.to_raster(DEM_EXPORT_FOLDER + "parcels\\input\\" + index + "_compare.tif")
    dem_diff.rio.to_raster(DEM_EXPORT_FOLDER + "parcels\\difference\\" + index + ".tif")


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
    continue

    #dem_record = rio.open(compare_model_path)
    #out_image_record, transformed_record = mask(dem_record, [mask_parcel], crop=True, filled=True, pad=True)
    #dem_record_array = out_image_record.astype('float64')

    #dem_array = dem_record_array - dem_base_array
    
    fig, ax = plt.subplots(1, ncols=4, figsize=(12, 12))

    base_dem.plot(ax=ax[0])
    repr_compare.plot(ax=ax[1])
    dem_diff.plot(ax=ax[2])
    dem_diff.plot.hist(ax=ax[3])
    #show(out_image_base, cmap='rainbow', vmin=390, ax=ax[0])
    #show(dem_record, cmap='rainbow', vmin=390, ax=ax[1])
    #show(dem_array, cmap='rainbow', vmin=390, ax=ax[0])
    plt.show()

    break

# export geojson file
with open(parcel_geojson_path, 'w', encoding='utf8') as pf:
    json.dump(parcel_geojson, pf, indent=4)
    print("The probed area dimensions where exported to {}".format(parcel_geojson_path))

print("================================")
print("Finished task. Check {} for results.".format(task_csv_file_out))
print("================================")
# write result to result csv
tasks_df.to_csv(task_csv_file_out, sep=";", decimal=",")