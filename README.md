# AutoDEM
Metashape Script to generate digital elevation models from UAV images

## Main Features
- Automatic mission detection from directory structure, import based on record time and location
- Every record date gets imported as seperate chunk
- Fully automatic detection of ground control points (=GCP) with opencv for georeferencing
- Marker pinning based on found ground control points
- image processing and export of elevation model as TIFF
- Creates a export folder containing all elevation models, logfile and processing statistic

    

## Installation 
**IMPORTANT**
This script requires some python modules installed maually in metashape.

Run following commands on the machine where Agisoft Metashape is installed:

Go in the directory where Metashape is installed
```
cd C:\Program Files\Agisoft\Metashape Pro\python
```
Now call python to install the required librarys
```
python.exe -m pip install cv2
python.exe -m pip install pandas
python.exe -m pip install rasterio
```


Created by: Hannes Bosch 2023 University of Hohenheim



