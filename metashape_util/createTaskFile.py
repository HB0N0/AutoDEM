import csv
import Metashape
from metashape_util.file_utils import FileUtils
from metashape_util.chunk import ChunkUtils

app = Metashape.Application()
doc = app.document

output_file = "J:\\440a\\HiWi\\Allgemein\\Bosch\\Python\\compare_dem\\compare_dem.CSV"

base_models = [
    "2022-03-23_R1",
    "2022-06-17_R1"
]

FIELD_PARCELS = FileUtils.read_geocoord_files({
    "aufwuchs1": "J:\\440a\\HiWi\\Allgemein\\Bosch\\Python\\2022_Messprotokoll_Geodaten_Hohenheim_1.Aufwuchs.csv",
    "aufwuchs2": "J:\\440a\\HiWi\\Allgemein\\Bosch\\Python\\2022_Messprotokoll_Geodaten_Hohenheim_2.Aufwuchs.csv",
})


with open(output_file, "w", newline='') as csv_file:
    writer = csv.writer(csv_file, delimiter=";")
    writer.writerow(["Bezeichnung", "Basismodell", "Aufzeichnung", "Parzelle", "Index N", "Index O", "Geo Koordinaten"])

    bm = 0
    for chunk in doc.chunks[1:]:
        bm += 1

        field_date, field_name = ChunkUtils.parseChunkName(chunk.label)

        for parcel in FIELD_PARCELS["aufwuchs1"][field_name]:
            if(parcel in ["GCP", "BS"]): continue

            bez = "BM{}P{}{}".format(bm, parcel, bm-1)

            writer.writerow([bez, doc.chunks[0].label, chunk.label, parcel, bm - 1, 0, "aufwuchs1"])
