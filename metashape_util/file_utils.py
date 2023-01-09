import os
import csv
from collections import defaultdict
import warnings

class FileUtils:
	def parsePath(path):
		path_head, path_tail = os.path.split(path)
		name, ext = os.path.splitext(path_tail)

		return {
			"base_folder": path_head,
			"filename": path_tail,
			"name": name,
			"extension": ext
		}

	def createDirsIfNotExists(path):
		if not os.path.exists(path):
			os.makedirs(path)
			print("Export dir created: " + path)

	def read_geocoord_file(csv_file):
		# reads geocoordiante csv file
		parcel_obj = defaultdict(lambda: defaultdict(dict))

		if not os.path.exists(csv_file):
			warnings.warn("Geocoord file not found: {}".format(csv_file))
			return {}

		with open(csv_file, newline='') as csvfile:
			points_reader = list(csv.reader(csvfile, delimiter=';', quotechar='"'))

			for row in points_reader[1:]:
				if row[0] == "" or row[4] == "" or row[5] == "" or row[6] == "": continue
				betr = row[0]
				field = row[1].partition("/")[0]
				label = row[2]
				p_type = row[3]
				lon = float(row[4].replace(",", "."))
				lat = float(row[5].replace(",", "."))
				alt = float(row[6].replace(",", "."))

				parcel_obj[field].setdefault(p_type, []).append(np.array([lon, lat, alt]))

		return dict(parcel_obj)

	def read_geocoord_files(csv_files):
		# reads all specified geocoord files, returns indexed dict
		res = {}
		for key,value in csv_files.items():
			res[key] = FileUtils.read_geocoord_file(value)
		return res