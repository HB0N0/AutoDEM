import numpy as np
import math

class GeoUtils:
	def orderRectPoints(l):
		# Order rectangle points counter clockwise
		mlat = sum(x[0] for x in l) / len(l)
		mlng = sum(x[1] for x in l) / len(l)
		def algo(x):
			return (math.atan2(x[0] - mlat, x[1] - mlng) + 2 * math.pi) % (2*math.pi)
		l.sort(key=algo)
		return l
		# Credit: https://stackoverflow.com/questions/1709283/how-can-i-sort-a-coordinate-list-for-a-rectangle-counterclockwise#answer-1709546

	def toNumpy(l):
		"""loops list and converts every item to numpy array"""
		return [np.array(i) for i in l]

	def haversine_np(lon1, lat1, lon2, lat2):
		"""
		Calculate the great circle distance between two points
		on the earth (specified in decimal degrees)

		All args must be of equal length.    

		"""
		lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

		dlon = lon2 - lon1
		dlat = lat2 - lat1

		a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2

		c = 2 * np.arcsin(np.sqrt(a))
		km = 6367 * c
		return km

	def coordinateDistanceMeters(c1, c2):
		"""calculate distance of two (2D) coordinates in meters"""
		return GeoUtils.haversine_np(c1[0], c1[1], c2[0], c2[1]) * 1000

	def vToPoint(point, direction, distance):
		"""Returns vector, starting from point1 in direction of point2. The resulting vector has length of given distance in meters"""
		v = direction - point
		v_meters = GeoUtils.coordinateDistanceMeters(point, direction)
		return (distance / v_meters) * v

	TILE_MODE_PARALLEL = 0 
	"""Tile borders are parallel to the west and south parcel border. This mode is recommended, all parcels have exact the same size"""
	TILE_MODE_FOLLOW_NORTH = 1
	"""Tile borders are parallel to south parcel border. South-North borders follow west and east side of the parcel"""
	TILE_MODE_FOLLOW_EAST = 2
	"""Tile borders are parallel to east border. West-East borders follow north and south side of the parcel"""
	TILE_MODE_FOLLOW_BOTH = 3
	"""Tile borders are parallel to east border. West-East borders follow north and south side of the parcel"""

	def getParcelTile(parcel, x_index = 0, y_index = 0, tile_mode = TILE_MODE_PARALLEL, tile_size_x_m = 1, tile_size_y_m = 1, tile_origin = "SW"):
		vToPoint = GeoUtils.vToPoint
		SO, SW, NW, NO = parcel
		if tile_mode == GeoUtils.TILE_MODE_FOLLOW_NORTH:
			tile_size_x = np.max([GeoUtils.coordinateDistanceMeters(SW, SO), GeoUtils.coordinateDistanceMeters(NW, NO)])
			return [
				SO + vToPoint(SO, NO, (x_index * tile_size_y_m)) + vToPoint(SW, SO, (y_index * tile_size_x)),
				SW + vToPoint(SW, NW, (x_index * tile_size_y_m)) + vToPoint(SW, SO, (y_index * tile_size_x)),
				SW + vToPoint(SW, NW, (x_index * tile_size_y_m) + tile_size_y_m) + vToPoint(SW, SO, (y_index * tile_size_x)),
				SO + vToPoint(SO, NO, (x_index * tile_size_y_m) + tile_size_y_m) + vToPoint(SW, SO, (y_index * tile_size_x)),
			] # Point order [SO,SW,NW,NO]
		elif tile_mode == GeoUtils.TILE_MODE_FOLLOW_EAST:
			tile_size_y = np.max([GeoUtils.coordinateDistanceMeters(SW, NW), GeoUtils.coordinateDistanceMeters(SO, NO)])
			return [
				SW + vToPoint(SW, NW, (x_index * tile_size_y)) + vToPoint(SW, SO, (y_index * tile_size_x_m) + tile_size_x_m),
				SW + vToPoint(SW, NW, (x_index * tile_size_y)) + vToPoint(SW, SO, (y_index * tile_size_x_m)),
				NW + vToPoint(SW, NW, (x_index * tile_size_y)) + vToPoint(NW, NO, (y_index * tile_size_x_m)),
				NW + vToPoint(SW, NW, (x_index * tile_size_y)) + vToPoint(NW, NO, (y_index * tile_size_x_m) + tile_size_x_m),
			] # Point order [SO,SW,NW,NO]
		elif tile_mode == GeoUtils.TILE_MODE_FOLLOW_BOTH:
			tile_size_y_p = np.max([GeoUtils.coordinateDistanceMeters(SW, NW), GeoUtils.coordinateDistanceMeters(SO, NO)])
			tile_size_y = tile_size_y_p / round(tile_size_y_p)
			tile_size_x_p = np.max([GeoUtils.coordinateDistanceMeters(SW, SO), GeoUtils.coordinateDistanceMeters(NW, NO)])
			tile_size_x = tile_size_x_p / round(tile_size_x_p)
			return [
				SO + vToPoint(SO, NO, (x_index * tile_size_y)) + vToPoint(SW, SO, (y_index * tile_size_x)),
				SW + vToPoint(SW, NW, (x_index * tile_size_y)) + vToPoint(SW, SO, (y_index * tile_size_x)),
				SW + vToPoint(SW, NW, (x_index * tile_size_y)+ tile_size_y) + vToPoint(NW, NO, (y_index * tile_size_x)),
				SO + vToPoint(SO, NO, (x_index * tile_size_y)+ tile_size_y) + vToPoint(NW, NO, (y_index * tile_size_x)),
			] # Point order [SO,SW,NW,NO]
		elif tile_mode == GeoUtils.TILE_MODE_PARALLEL:
			if(tile_origin not in ["SW", "SO"]):
				print("Only Origni Points [SW] and [SO] are avaliable at the moment, resetting to [SW]")
				tile_origin = "SW"

			if(tile_origin == "SW"):
				return [
					SW + vToPoint(SW, NW, (x_index * tile_size_y_m)) + vToPoint(SW, SO, (y_index * tile_size_x_m) + tile_size_x_m),
					SW + vToPoint(SW, NW, (x_index * tile_size_y_m)) + vToPoint(SW, SO, (y_index * tile_size_x_m)),
					SW + vToPoint(SW, NW, (x_index * tile_size_y_m) + tile_size_y_m) + vToPoint(SW, SO, (y_index * tile_size_x_m)),
					SW + vToPoint(SW, NW, (x_index * tile_size_y_m) + tile_size_y_m) + vToPoint(SW, SO, (y_index * tile_size_x_m) + tile_size_x_m),
				] # Point order [SO,SW,NW,NO]
			if(tile_origin == "SO"):
				return [
					SO + vToPoint(SO, NO, (x_index * tile_size_y_m)) + vToPoint(SW, SO, (y_index * tile_size_x_m)),
					SO + vToPoint(SO, NO, (x_index * tile_size_y_m)) + vToPoint(SW, SO, (y_index * tile_size_x_m) - tile_size_x_m),
					SO + vToPoint(SO, NO, (x_index * tile_size_y_m) + tile_size_y_m) + vToPoint(SW, SO, (y_index * tile_size_x_m) - tile_size_x_m),
					SO + vToPoint(SO, NO, (x_index * tile_size_y_m) + tile_size_y_m) + vToPoint(SW, SO, (y_index * tile_size_x_m)),
				] # Point order [SO,SW,NW,NO]

