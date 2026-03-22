import arcpy
import os

class Toolbox(object):
    def __init__(self):
        self.label = "Utility Network Auto Tools"
        self.alias = "un_auto_tools"
        self.tools = [AutoServiceTerritoryFix]


class AutoServiceTerritoryFix(object):

    def __init__(self):
        self.label = "AUTO FIX Service Territory (Utility Network Ready)"
        self.description = "Generate Service Territory otomatis + fix semua requirement Utility Network"

    def getParameterInfo(self):

        # INPUT MULTIPLE LAYER
        p1 = arcpy.Parameter(
            displayName="Input Layers",
            name="in_layers",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )

        # FEATURE DATASET TARGET
        p2 = arcpy.Parameter(
            displayName="Target Feature Dataset",
            name="target_fd",
            datatype="DEFeatureDataset",
            parameterType="Required",
            direction="Input"
        )

        # OUTPUT NAME
        p3 = arcpy.Parameter(
            displayName="Output Name",
            name="out_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        p3.value = "SERVICE_AREA"

        return [p1, p2, p3]


    def execute(self, parameters, messages):

        layers = parameters[0].valueAsText.split(";")
        target_fd = parameters[1].valueAsText
        out_name = parameters[2].valueAsText

        arcpy.AddMessage("🚀 START AUTO FIX SERVICE TERRITORY")

        xmin, ymin, xmax, ymax = None, None, None, None
        sr = None

        # =========================
        # VALIDASI + AMBIL EXTENT
        # =========================
        for lyr in layers:
            desc = arcpy.Describe(lyr)

            if desc.shapeType not in ["Point", "Polyline", "Polygon"]:
                arcpy.AddWarning(f"⚠ Skip {lyr} (bukan feature layer)")
                continue

            ext = desc.extent

            if xmin is None:
                xmin, ymin, xmax, ymax = ext.XMin, ext.YMin, ext.XMax, ext.YMax
                sr = desc.spatialReference
            else:
                xmin = min(xmin, ext.XMin)
                ymin = min(ymin, ext.YMin)
                xmax = max(xmax, ext.XMax)
                ymax = max(ymax, ext.YMax)

        if xmin is None:
            arcpy.AddError("❌ Tidak ada layer valid")
            return

        arcpy.AddMessage("📐 Extent berhasil dihitung")

        # =========================
        # CREATE POLYGON
        # =========================
        array = arcpy.Array([
            arcpy.Point(xmin, ymin),
            arcpy.Point(xmin, ymax),
            arcpy.Point(xmax, ymax),
            arcpy.Point(xmax, ymin),
            arcpy.Point(xmin, ymin)
        ])

        polygon = arcpy.Polygon(array, sr, True, True)  # Z & M ENABLED

        # =========================
        # OUTPUT PATH
        # =========================
        output_fc = os.path.join(target_fd, out_name)

        if arcpy.Exists(output_fc):
            arcpy.AddMessage("♻ Menghapus existing SERVICE AREA...")
            arcpy.Delete_management(output_fc)

        # =========================
        # CREATE FEATURE CLASS (FIX)
        # =========================
        arcpy.AddMessage("🧱 Membuat Feature Class (Z&M Enabled)...")

        arcpy.CreateFeatureclass_management(
            out_path=target_fd,
            out_name=out_name,
            geometry_type="POLYGON",
            spatial_reference=sr,
            has_m="ENABLED",
            has_z="ENABLED"
        )

        # =========================
        # INSERT
        # =========================
        with arcpy.da.InsertCursor(output_fc, ["SHAPE@"]) as cursor:
            cursor.insertRow([polygon])

        # =========================
        # REPAIR GEOMETRY
        # =========================
        arcpy.AddMessage("🛠 Repair Geometry...")
        arcpy.RepairGeometry_management(output_fc)

        # =========================
        # VALIDASI FINAL
        # =========================
        desc = arcpy.Describe(output_fc)

        if not desc.hasZ or not desc.hasM:
            arcpy.AddError("❌ Gagal: Z/M tidak aktif")
            return

        if desc.shapeType != "Polygon":
            arcpy.AddError("❌ Gagal: Bukan polygon")
            return

        arcpy.AddMessage("✅ VALIDASI LOLOS")
        arcpy.AddMessage("🔥 SERVICE TERRITORY SIAP UNTUK UTILITY NETWORK")