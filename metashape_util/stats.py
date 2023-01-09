import os
import csv
import pandas as pd

class Stats:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        if not os.path.exists(csv_path):
            with open(csv_path, "w") as csv_file:
                writer = csv.writer(csv_file, delimiter=";")
                writer.writerow(["Chunk Name"])
            
        self.df = pd.read_csv(self.csv_path, index_col='Chunk Name', delimiter=";", decimal=",")

    def setValue(self, row, col, value):
        if(hasattr(row, "label")): 
            index = row.label
        else: 
            index = row
        self.df.loc[index, col] = self.castValue(value)

    def castValue(self, value):
        return str(value).replace(".", ",")
    
    def getValue(self, row, col, value):
        return self.df.loc[row, col]
	
    def saveFile(self):
        self.df.to_csv(self.csv_path, sep=";", decimal=",", )

    def saveChunkMeta(self, chunk):
        # Extract chunk meta data and save to file
        # chunk object
        self.setValue(chunk.label, "Chunk/camera_count", len(chunk.cameras))
        self.setValue(chunk.label, "Chunk/marker_count", len(chunk.markers))
        self.setValue(chunk.label, "Chunk/OptimizeCameras/sigma0", chunk.meta["OptimizeCameras/sigma0"])
        self.setValue(chunk.label, "Chunk/AlignCameras/duration", chunk.meta["AlignCameras/duration"])
        # point cloud meta
        self.setValue(chunk.label, "PointCloud/MatchPhotos/duration", chunk.point_cloud.meta["MatchPhotos/duration"])
        self.setValue(chunk.label, "PointCloud/point_count", len(chunk.point_cloud.points))
        # dense cloud meta
        self.setValue(chunk.label, "DenseCloud/duration", chunk.dense_cloud.meta["BuildDenseCloud/duration"])
        self.setValue(chunk.label, "DenseCloud/resolution", chunk.dense_cloud.meta["BuildDenseCloud/resolution"])
        # depth maps meta
        self.setValue(chunk.label, "DepthMaps/duration", chunk.depth_maps.meta["BuildDepthMaps/duration"])
        # orthomosaic meta
        self.setValue(chunk.label, "Orthomosaic/duration", chunk.orthomosaic.meta["BuildOrthomosaic/duration"])
        # DEM meta
        self.setValue(chunk.label, "BuildDem/duration", chunk.elevations[0].meta["BuildDem/duration"])
        self.setValue(chunk.label, "BuildDem/resolution", chunk.elevations[0].meta["BuildDem/resolution"])