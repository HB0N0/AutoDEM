# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Hannes Bosch
# Created Date: 2022-11-08
# version ='1.0'
# ---------------------------------------------------------------------------
""" Detect the pixel location of visible ground control points in given image"""

import math
import cv2
import numpy as np


class GcpDetector:
    def __init__(self, image = False):
            if(image != False):
                self.image = image

    def processImage(self, image = False):
        if(image == False):
            image = self.image
        if(image == False):
            raise Exception("No image specified")

        img = cv2.imread(image)
        img_sat = self._filterPixelsBySaturation(img)
        img_gray = cv2.cvtColor(img_sat, cv2.COLOR_BGR2GRAY)

        pts = self._findKeyPoints(img_gray)
        if(len(pts) <= 0): return False
        
        guess_point = self._getBestMatchingKeyPoint(pts)
        if(guess_point == False): return False

        print(guess_point)

        crop_size = 16
        crop = self._cropImageAroundPoint(img_gray, guess_point, crop_size)

        gcpCenter = self._findCenterOfObject(crop)

        if(gcpCenter == False): return False

        isGCP = self._checkGcpShape(gcpCenter, crop)

        if(not isGCP):
            return False

        # we know this point is a gcp, now we need the coordinates in the real image instead of the cropped
        centerX = guess_point[0] - crop_size + gcpCenter[0]
        centerY = guess_point[1] - crop_size + gcpCenter[1]
        return centerX, centerY
        

    def _filterPixelsBySaturation(self, img):
        # preparing the mask to overlay
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([0, 0, 100]), np.array([255, 50, 255]))
        # The black region in the mask has the value of 0,
        # so when multiplied with original image removes all non-gray regions
        return cv2.bitwise_and(img, img, mask = mask)

    def _findKeyPoints(self, img):
        # Create ORB keypoint detector
        orb = cv2.ORB_create(edgeThreshold=15, patchSize=31, nlevels=8, fastThreshold=20, scaleFactor=12/10, WTA_K=2,scoreType=cv2.ORB_HARRIS_SCORE, firstLevel=0, nfeatures=6 )

        # find the keypoints with ORB
        kp = orb.detect(img,None)

        # compute the descriptors with ORB
        kp, des = orb.compute(img, kp)  ### TODO if this works with graysacle

        pts = cv2.KeyPoint_convert(kp)
        return pts

    def _getBestMatchingKeyPoint(self, pts):
        weighted_points = self._getWeightedPointsByDistance(pts)

        if(len(weighted_points) > 1):
            # take the first 2 points and calculate average point
            best_weighted_points, w = zip(*weighted_points[:2 ])
        else:
            return False

        print(best_weighted_points)

        avg_point = self._avgPoint(best_weighted_points)
        return avg_point

    def _getWeightedPointsByDistance(self, pts):
        z = np.array([complex(p[0], p[1]) for p in pts])
        out = abs(z[..., np.newaxis] - z) # calculate distances to other points
        sum = np.sum(out, axis=1) # sum distances to all other points per point -> 2d array

        weighted_points = list(zip(pts, sum))
        weighted_points.sort(key=lambda tup: tup[1])
        return weighted_points

    def _avgPoint(self, pts):
        # take the best weighted poits and calculate center (avg)
        return [int(sum(x)/len(x)) for x in zip(*pts)] 

        


    def _cropImageAroundPoint(self, img, center, crop_size):
        xMin = self._clamp(center[1]-crop_size, 0, len(img[0]))
        xMax = self._clamp(center[1]+crop_size, 0, len(img[0]))
        yMin = self._clamp(center[0]-crop_size, 0, len(img[1]))
        yMax = self._clamp(center[0]+crop_size, 0, len(img[1]))
        cropped_img = img[xMin:xMax, yMin:yMax]
        return cropped_img

    def _clamp(self, num, min_value, max_value):
        num = max(min(num, max_value), min_value)
        return num

    def _findCenterOfObject(self, img):
        #find center
        # calculate moments of binary image
        M = cv2.moments(img)
        # calculate x,y coordinate of center (coordinates are of cropped image)
        if(M["m00"] == 0): return False

        cX = M["m10"] / M["m00"]
        cY = M["m01"] / M["m00"]
        return [cX, cY]

    def _checkGcpShape(self, center, img):
        # First threshold image to get binary image (and detect the white spots)
        thresh, img = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY)
        

        #check if surroundings match a hourglass or chess field shape
        gcp_matched = False
        r = 5 # check pixels with a radius of 5
        # if basic shape is matched check also 
        min_degrees = 30
        min_radians = min_degrees * math.pi / 180


        # loop from -3.14 to +3.14 (to get all points circular around the center)
        match_start = False
        for a in np.arange(- math.pi, math.pi, 0.1):
            gcp_matched = self._crossDetect(img, center, a, r)
            if(gcp_matched == True and match_start == False):
                match_start = a
            if(gcp_matched == False and match_start != False):
                #end of match
                if(abs(match_start - a) > min_radians):
                    gcp_matched = True
                else:
                    gcp_matched = False
                break


        return gcp_matched

    def _crossDetect(self, img, center, angle = 0, r = 5):
        cX, cY = center

        checkX = round(cX + math.sin(angle) * r)
        checkY = round(cY + math.cos(angle) * r)
        try:
            # for each point check if the pixel is black
            if(all(img[checkY, checkX] == (0,0,0))):
                # if pixel is black check if opposite point is also black
                oppX = round(cX + math.sin(angle + math.pi) * r)
                oppY = round(cY + math.cos(angle + math.pi) * r)
                if(all(img[oppY, oppX] == (0,0,0))):
                    # when check and opposide points are both black,
                    # the left and right points on the circle must be white (in case of an GCP)
                    leftX = round(cX + math.sin(angle + math.pi*0.5) * r)
                    leftY = round(cY + math.cos(angle + math.pi*0.5) * r)

                    rightX = round(cX + math.sin(angle + math.pi*1.5) * r)
                    rightY = round(cY + math.cos(angle + math.pi*1.5) * r)
                    if(all(img[leftY, leftX] != (0,0,0)) and all(img[rightY, rightX] != (0,0,0))):
                        return True
            return False
        except IndexError:
            return False