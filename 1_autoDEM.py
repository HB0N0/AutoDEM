import Metashape
import argparse
from pprint import pprint
from collections import defaultdict
import os, sys, time, re
import configparser
from datetime import datetime

from metashape_util.chunk import ChunkUtils
from metashape_util.dialog import Dialog 
from metashape_util.file_utils import  FileUtils
from metashape_util.stats import  Stats
from metashape_util.email_notify import EmailNotify

from gcp_detector.gcpToMarker import GcpToMarker

# in metashape args:
#   --year 2022 --field R1 --refpath "J:\440a\HiWi\Allgemein\Stumpe\DiWenkLa\03_Versuchsflächen\Koordinaten_GCP_R1.txt"

app = Metashape.Application()
doc = app.document
dialog = Dialog(app)
gcpToMarker = GcpToMarker()

#config parser
config = configparser.ConfigParser()
config.read(sys.path[0] + "\config.ini")

#setup email configuration
notify = EmailNotify(config["EmailNotify"])

start_time = datetime.now()



try:
	doc.save()
except OSError:
	raise Exception("Error while trying to save the project file. \r\n Please chose \"save as\" and save project under a memoriable name in a proper location.")

documentFile = FileUtils.parsePath(doc.path)

# CONFIG
MARKER_MAX_ERROR_METERS = config["Defaults"].getfloat("MARKER_MAX_ERROR_METERS", 0.1)
MARKER_MIN_PINS = config["Defaults"].getint("MARKER_MIN_PINS", 0)

DEM_EXPORT_FOLDER = os.path.expanduser(config["Defaults"].get("DEM_EXPORT_FOLDER", "~\\Desktop\\autoDEM\\"))
DEM_EXPORT_FOLDER += documentFile['name'] + "\\"

FileUtils.createDirsIfNotExists(DEM_EXPORT_FOLDER)

# stats file containing 
STATS_FILE = DEM_EXPORT_FOLDER + "stats.csv"
stats = Stats(STATS_FILE)

LOG_FILE = DEM_EXPORT_FOLDER + time.strftime("%Y%m%d-%H%M%S") + "- log.txt"
Metashape.app.settings.log_enable = True
Metashape.app.settings.log_path = LOG_FILE


parser = argparse.ArgumentParser()
parser.add_argument('--import-new', dest='import_new', type=bool, help='Work with existing chunks or import new data')
parser.add_argument('--recpath', dest='records_path', type=str, help='Directory to scan for records')
parser.add_argument('--import-only', dest='import_only', type=bool, help='Only creates the chunks and basic camera aligning, no processing', default=False)
parser.add_argument('--refpath', dest='reference_path', type=str, help='Path to file containing GCP references')
parser.add_argument('--year', dest='year', type=str, help='Year of records to import, read from folder name')
parser.add_argument('--field', dest='field', type=str, help='Field to import, must match folder name')
args = parser.parse_args()

if(len(doc.chunks) <= 1):
	import_new = True
elif(args.import_new is None):
	import_new = app.getBool("Sollen neue Daten importiert werden?")
else:
	import_new = args.import_new

if(import_new or args.import_only):

	BASE_PATH = args.records_path or app.getExistingDirectory("Select Folder with records")
	print("Scanning directory: " + BASE_PATH)

	if(BASE_PATH.strip() == ""):
		raise Exception("Please define a directory to scan for records")

	def scan_records_dir(path): 
		records = defaultdict(lambda: defaultdict(dict))
		for entry in os.scandir(path):
			if (entry.is_dir()):
				# Regex checks subdir names and excludes malformatted and "Kalibrierung" / "Kalibartion"
				match_pattern = re.match(r"(\d{4}\-\d{2}\-\d{2})[\s\_]((?!Kal).+$)", entry.name, re.IGNORECASE) 
				if (match_pattern):
					entry_name = match_pattern.group(2)
					entry_date = match_pattern.group(1)
					entry_year = entry_date[:4]
					
					records[entry_year][entry_name][entry_date] = entry.path # records[name] = date
		return dict(records)
		
	# Read all records from specified directory
	avaliable_records = scan_records_dir(BASE_PATH)
	#pprint(avaliable_records.keys())


	# Let user select year and field to import
	# if already given by console args no dialog will open
	if(args.year and not args.year in avaliable_records): 
		args.year = False
	year = args.year or dialog.getListCoice(list(avaliable_records.keys()), "Wähle das Jahr", len(avaliable_records))
	print("Selected: " + year)

	if(args.field and not args.field in avaliable_records[year]): 
		args.field = False
	field = args.field or dialog.getListCoice(list(avaliable_records[year].keys()), "Wähle den Schlag", 1)
	print("Selected: " + field)

	records = avaliable_records[year][field]

	# Remove all empty chunks (empty document has usually only one default chunk)
	for chunk in list(doc.chunks):
		if not len(chunk.cameras):
			doc.remove(chunk)

	photos_list = {}

	# Prompt user for file containing reference points to import in each chunk
	ref_file = args.reference_path or app.getOpenFileName("Wähle Marker-Datei", filter="*.txt")

	# create chunk for each date a record exists
	print("Creating chunks...")

	for rec in records:
		# first create new chunk
		chunk = doc.addChunk()
		chunk.label = rec + "_" + field  # label is [date]_[field]
		
		base_path = records[rec]
		photos_list[rec] = []

		# get images from dir
		for mission in os.scandir(base_path):
			if(mission.is_dir() and re.search(r"FPLAN", mission.name)): # only scan mission directorys for files
				for file in os.scandir(mission.path):
					if(file.name.rsplit(".", 1)[1].upper() in ["JPG", "JPEG"]): # only import jpg images
						photos_list[rec].append(file.path)
						
		chunk.addPhotos(photos_list[rec])
		
		if(ref_file):
			chunk.importReference(path=ref_file, delimiter="\t", format=Metashape.ReferenceFormatCSV, columns="nxyz", create_markers=True)
		app.update()

	doc.save()
	
if (args.import_only):
	quit(True) # Not working properly
	raise Exception("Script ended successful after import")
	
# align photos
for chunk in list(doc.chunks):
	if chunk.enabled == False: continue
	if not ChunkUtils.hasChunkPointCloud(chunk):
		chunk.matchPhotos(downscale=1, keypoint_limit=40000, tiepoint_limit=0)
	else:
		print("PointCloud already exists in Chunk: " + chunk.label, ", skipping")
	if not ChunkUtils.areCamerasAligned(chunk):
		chunk.alignCameras()
	else:
		print("Cameras already aligned in Chunk: " + chunk.label, ", skipping")
	
doc.save()
app.update()



# for each chunk match gcps
for chunk in doc.chunks:
	if chunk.enabled == False: continue
	if(not ChunkUtils.areMarkersPinned(chunk)):
		print("Detecting GCPs in chunk: " + chunk.label + "...")
		gcp_start = time.time()
		gcpToMarker.processChunk(chunk)
		print("Finished, Operation took: " + str(time.time() - gcp_start) + " secounds")
		stats.setValue(chunk, "GcpToMarker/duration", time.time() - gcp_start)
	else:
		print("Markers already pinned in Chunk: " + chunk.label, ", skipping GCP detection")
	app.update()

stats.saveFile()

doc.save()
gcp_failed_chunks = []
# build surface model
for chunk in doc.chunks:
	if chunk.enabled == False: continue

	# Skip already exported chunks (check if tif file exists)
	dem_export_path = DEM_EXPORT_FOLDER + chunk.label + ".tif"
	if(os.path.exists(dem_export_path)):
		print("DEM file already exists for chunk: " + chunk.label, ", skipping export.")
		print("Move or delete output file to create new export.")
		continue

	# Check Error level and only continue if error level is under max value
	# If error level is to high chunk processing is skipped
	chunk_marker_error = ChunkUtils.getReferenceTotalError(chunk)
	stats.setValue(chunk, "GcoToMarker/Marker_error", chunk_marker_error)

	# Check how many pins each marker has (only for stats)
	marker_pins = ChunkUtils.getPinnedMarkersCount(chunk)
	for marker,count in marker_pins.items():
		stats.setValue(chunk, "GcpToMarker/Markers/"+marker, count)
	
	chunk_min_marker_pins = min(marker_pins.values())

	stats.saveFile()

	if(chunk_marker_error >= MARKER_MAX_ERROR_METERS):
		gcp_failed_chunks.append((chunk, chunk_marker_error, chunk_min_marker_pins))
		print("Skipping chunk " + chunk.label + " due inaccurate marker positions")
		continue

	if(chunk_min_marker_pins < MARKER_MIN_PINS):
		gcp_failed_chunks.append((chunk, chunk_marker_error, chunk_min_marker_pins))
		print("Skipping chunk " + chunk.label + " due to few marker projections")
		continue

	# Ensure that the model is optimized from GCPs
	# Update Model
	chunk.updateTransform()

	if(len(chunk.dense_clouds) <= 0):
		# Optimize Cameras
		# !!!IMPORTANT this deletes all dense clouds and depth maps - only use on not already exported chunks!!
		chunk.optimizeCameras() 

		# Downscale is what is named "quality" in GUI. Where 0 - is Ultra, 1 - High, 2 - Medium, 4 - Low.
		chunk.buildDepthMaps(
            downscale = 1, 
            filter_mode = Metashape.FilterMode.ModerateFiltering
        )
		chunk.buildDenseCloud(
            point_colors = True
        )
	else:
		print("Dense Cloud found in chunk: " + chunk.label, ", skipping")

	if(len(chunk.elevations) <= 0):
		chunk.buildDem(
			source_data=Metashape.DenseCloudData, 
			interpolation=Metashape.EnabledInterpolation
        )
	else:
		print("Elevation Model found in chunk: " + chunk.label, ", skipping")

	if(len(chunk.orthomosaics) <= 0):
		chunk.buildOrthomosaic(
            surface_data = Metashape.DataSource.ElevationData, 
            blending_mode = Metashape.BlendingMode.MosaicBlending, 
            fill_holes=True
        )
	else:
		print("Orthomosaic found in chunk: " + chunk.label, ", skipping")

    # Export DEM

	chunk.exportRaster(
		path = dem_export_path,
		image_format = Metashape.ImageFormat.ImageFormatTIFF,
		save_world = True,
		source_data = Metashape.DataSource.ElevationData
	)


	stats.saveChunkMeta(chunk)
	stats.setValue(chunk, "dem_export_path", dem_export_path)
	stats.saveFile()

doc.save()
end_time = datetime.now()			


gcp_failed_text = ""
if(len(gcp_failed_chunks) > 0 ):
	gcp_failed_text +=  "WARNING -----------------------------------------------------\n"
	gcp_failed_text += "Auto GCP detection was to unaccurate in following chunks: \n"
	for failed in gcp_failed_chunks:
		gcp_failed_text += "\t" + failed[0].label + " Error:" + str(failed[1]) + " Min Marker Projections:" + str(failed[2]) + "\n"
	gcp_failed_text += "Try to correct marker locations by hand and run this script again\n"
	gcp_failed_text += "Successful chunks will be ignored and not proccessed again\n"
	gcp_failed_text += "-------------------------------------------------------------\n"


result = """
######################################
Finished job: processing aerial photos
The job took: {duration}
{gcp_failed_text}
The exported elevation models (if any) are located in: 
{export_dir}
######################################
""".format(duration=(end_time - start_time), gcp_failed_text = gcp_failed_text, export_dir=DEM_EXPORT_FOLDER)

print(result)

#send email notification
notify.notify("Job finished! {}".format(documentFile['name']), result)

