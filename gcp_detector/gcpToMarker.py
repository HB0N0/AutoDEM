import Metashape
from pprint import pprint
from gcp_detector.gcpDetector import GcpDetector

app = Metashape.Application()
doc = app.document

gcpDetect = GcpDetector()

class GcpToMarker:
    def _init_(self, chunk = False):
        self.chunk = chunk

    def processChunk(self, chunk = False):
        if(chunk == False):
            chunk = self.chunk
        if(chunk == False):
            raise Exception("No Chunk specified.")

        # Setup shapes if not exist 
        # this is needed to draw the control points for visualisation on the map
        if not chunk.shapes:
            chunk.shapes = Metashape.Shapes()
            chunk.shapes.crs = chunk.crs

        # Next step is to loop through the cameras and try to detect a marker in every single image
        for camera in chunk.cameras:
            print("Processing " + camera.photo.path + "...")
            self._processCamera(chunk, camera)

        # Cleanup
        # Bad markers are outliers, for example points that are only detected in a single image
        self._unpinBadMarkers(chunk)

        # Update Model
        chunk.updateTransform()

        # Optimize Cameras
        chunk.optimizeCameras()

        
    def _processCamera(self, chunk, camera):
        # Process image and try to detect GCP
        foundGCP = gcpDetect.processImage(camera.photo.path)

        if(foundGCP != False):
            # This camera contains a GCP - append it to camera label (for debugging)
            camera.label += " [GCP]"

            gcp_pixel_coords = Metashape.Vector(foundGCP)

            # In the next step draw points in 3d world (with the matched gcps)
            # First calc 3d coordinates from image pixel coordinates
            point_internal = chunk.point_cloud.pickPoint(camera.center, camera.unproject(gcp_pixel_coords))
            gcp_3d_world = chunk.crs.project(chunk.transform.matrix.mulp(point_internal))
            # Then draw point at 3D coordinate
            shape = chunk.shapes.addShape()
            shape.geometry = Metashape.Geometry.Point(gcp_3d_world)

            # Next we estimate the nearest marker to the point by calculating distances from all markers
            distanceList = [] # (marker, distance)

            for marker in chunk.markers:
                # Get a copy of the points and set the Z-Coordinate to zero to eliminate height measurement errors
                marker_point = marker.reference.location.copy()
                marker_point.z = 0
                gcp_point = gcp_3d_world.copy()
                gcp_point.z = 0

                # Calc point distance
                distance = (marker_point - gcp_point).norm()
                # Create list of markers with distance as weight parameter
                distanceList.append((marker, distance))
            
            # Now we can sort the markers list by ascending distance (shortest first)
            distanceList.sort(key=lambda tup: tup[1], reverse=False)
            # The nearest marker is now our first list item
            bestMarker = distanceList[0][0]
            bestMarkerDistance = distanceList[0][1]

            # If distance to marker is under the distance threshould "pin" the marker
            if(bestMarkerDistance < 0.0003):
                bestMarker.projections[camera] = Metashape.Marker.Projection(gcp_pixel_coords, True)

            app.update()

    def _unpinBadMarkers(self, chunk, errorThreshold = 80000):
        # After setting markers automatically some of them may be false and increase the model error
        # This function unpins markers above a threshold level
        for marker in chunk.markers:
            for camera in chunk.cameras:
                # If marker is not pinned on this camera continue
                if not camera in marker.projections.keys():
                    continue

                # 2 dimensional vector of the marker projection on the photo
                v_proj = marker.projections[camera].coord 
                # 2 dimensional vector of projected 3D marker position
                v_reproj = camera.project(marker.position) 
                
                # Calc the reprojection error for current photo
                diff = (v_proj - v_reproj).norm() ** 2 
                    
                print(marker.label + " " + camera.label + "Error: " + str(diff))

                # Remove (Unpin) markers with error value above threshold
                if(diff > errorThreshold):
                    marker.projections[camera] = None
                    print("Removed bad marker on camera " + camera.label)