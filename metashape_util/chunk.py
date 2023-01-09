import re
import warnings
import Metashape

class ChunkUtils:

	def parseChunkName(name):
		field_name_match = re.match(r"(\d{4}\-\d{2}\-\d{2})[\s\_](.+)$", name, re.IGNORECASE)
		if not field_name_match: 
			warnings.warn("Chunkname {} doesnt match requirements YYYY-MM-DD_Schlagname. ".format(name))
			return False, False
		field_date = field_name_match.group(1)
		field_name = field_name_match.group(2)
		return field_date, field_name

	def areCamerasAligned(chunk):
		for camera in chunk.cameras:
			if camera.transform:
				return True
		return False

	def hasChunkPointCloud(chunk):
		if chunk.point_cloud:
			return True
		else:
			return False

	def areMarkersPinned(chunk):
		for marker in chunk.markers:
			if marker.projections:
				return True
		return False

	def getPinnedMarkersCount(chunk):
		pinned = dict()
		for marker in chunk.markers:
			pinned[marker.label] = len(marker.projections)
		return pinned

	def getReferenceTotalError(chunk):
		listErrors = []
		for marker in chunk.markers:
			if marker.position is None: continue
			source = marker.reference.location
			estim = chunk.crs.project(chunk.transform.matrix.mulp(marker.position))
			error = estim - source
			total = error.norm()
			print(marker.label, error.x, error.y, error.z, total)

			source = chunk.crs.unproject(marker.reference.location) #measured values in geocentric coordinates
			estim = chunk.transform.matrix.mulp(marker.position) #estimated coordinates in geocentric coordinates
			local = chunk.crs.localframe(chunk.transform.matrix.mulp(marker.position)) #local LSE coordinates
			error = local.mulv(estim - source)
			total = error.norm()
			
			sqareTotal = (total) ** 2
			listErrors += [sqareTotal]

		sumErrors = sum(listErrors)
		n = len(listErrors)
		if (n == 0): return None
		return (sumErrors / n) ** 0.5

	def drawPolygon(chunk, coordinates, label = False):
		if not chunk.shapes:
			chunk.shapes = Metashape.Shapes()
			chunk.shapes.crs = chunk.crs
		shape_crs = chunk.shapes.crs

		shape = chunk.shapes.addShape()
		if label: shape.label = label
		shape.geometry.type = Metashape.Geometry.Type.PolygonType
		shape.geometry = Metashape.Geometry.Polygon(coordinates)