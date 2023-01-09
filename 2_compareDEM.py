import Metashape
import numpy as np
import pandas as pd
import rasterio as rio
import rioxarray
import matplotlib.pyplot as plt
from metashape_util.file_utils import FileUtils
from metashape_util.geo_utils import GeoUtils
from metashape_util.chunk import ChunkUtils

app = Metashape.Application()
doc = app.document

documentFile = FileUtils.parsePath(doc.path)

# CONFIG
DEM_EXPORT_FOLDER = "C:\\Users\\Hiwi-440a\\Desktop\\"
DEM_EXPORT_FOLDER += documentFile['name'] + "\\"


# Read csv file
# Format: !!! First line is ignored (header line)
# Betrieb;       Versuchsfläche;     Bezeichnung Messpunkt/Dateiname;    Type;   Longitude;  Latitude;       Altitude
# Meiereihof;    R3/1;               R3/1 - GCP Nordost;                 GCP;    9,21929980; 48,71619670;    364,70
geocoord_csv_files = {
    "aufwuchs1": "J:\\440a\\HiWi\\Allgemein\\Bosch\\Python\\2022_Messprotokoll_Geodaten_Hohenheim_1.Aufwuchs.csv",
    "aufwuchs2": "J:\\440a\\HiWi\\Allgemein\\Bosch\\Python\\2022_Messprotokoll_Geodaten_Hohenheim_2.Aufwuchs.csv",
}

# this file contains any task data, which parcels shold be read
task_csv_file = DEM_EXPORT_FOLDER + "compare_dem.CSV"
# Bezeichnung;  Basismodell;    Aufzeichnung;   Parzelle;   Index N;    Index O;    Geo Koordinaten
# BM1PA;        2022-03-23_R1;  2022-03-29_R1;  A;          0;          0;          aufwuchs1

# the calculations results will be stored in this file. Format is the same as the tasks csv file
task_csv_file_out = DEM_EXPORT_FOLDER + "compare_dem_result.CSV"



# Constant var containing all parcel positions
FIELD_PARCELS = FileUtils.read_geocoord_files(geocoord_csv_files)

# Read tasks file
tasks_df = pd.read_csv(task_csv_file, index_col='Bezeichnung', delimiter=";", decimal=",")

# Loop through tasks and calculate result
for index, task in tasks_df.iterrows():
    print("Calculating Tile {}...".format(index))

    base_model_path = DEM_EXPORT_FOLDER + task["Basismodell"] + ".tif"
    compare_model_path = DEM_EXPORT_FOLDER + task["Aufzeichnung"] + ".tif"

    # Geo coord file falls back to first if not defined
    geo_coord_file = task["Geo Koordinaten"] or FIELD_PARCELS.keys()[0]

    # get the field name from the first chunk label
    field_date, field_name = ChunkUtils.parseChunkName(doc.chunks[0].label)
    
    # get raw parcel corner data
    parcel_full_u = FIELD_PARCELS[geo_coord_file][field_name][task["Parzelle"]]

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
    saveVal("Median", dem_diff.median().item())
    saveVal("Min", dem_diff.min().item())
    saveVal("Max", dem_diff.max().item())
    saveVal("25", dem_diff.quantile(0.25).item())
    saveVal("75", dem_diff.quantile(0.75).item())


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

# write result to result csv
tasks_df.to_csv(task_csv_file_out, sep=";", decimal=",")