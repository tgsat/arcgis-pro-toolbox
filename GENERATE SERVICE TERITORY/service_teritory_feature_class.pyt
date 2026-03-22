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

        try:
            arcpy.env.overwriteOutput = True

            # =========================
            # GET MULTIVALUE (FIX)
            # =========================
            vt = parameters[0].value

            layers = []
            for i in range(vt.rowCount):
                lyr = vt.getValue(i, 0)
                if arcpy.Exists(lyr):
                    layers.append(lyr)

            if not layers:
                raise Exception("Tidak ada layer valid")

            target_fd = parameters[1].valueAsText
            out_name = parameters[2].valueAsText
            output_fc = os.path.join(target_fd, out_name)

            arcpy.AddMessage(f"📊 Layer valid: {len(layers)}")

            xmin, ymin, xmax, ymax = None, None, None, None
            sr = None

            # =========================
            # EXTENT
            # =========================
            for lyr in layers:
                desc = arcpy.Describe(lyr)
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
                raise Exception("Extent gagal dihitung")

            # =========================
            # CREATE / UPDATE MODE
            # =========================
            if not arcpy.Exists(output_fc):

                arcpy.AddMessage("🆕 CREATE Service Territory")

                arcpy.CreateFeatureclass_management(
                    target_fd,
                    out_name,
                    "POLYGON",
                    spatial_reference=sr,
                    has_m="ENABLED",
                    has_z="ENABLED"
                )

            else:
                arcpy.AddMessage("♻ UPDATE Service Territory")

            # =========================
            # BUILD POLYGON
            # =========================
            arr = arcpy.Array()
            arr.add(arcpy.Point(xmin, ymin))
            arr.add(arcpy.Point(xmin, ymax))
            arr.add(arcpy.Point(xmax, ymax))
            arr.add(arcpy.Point(xmax, ymin))
            arr.add(arcpy.Point(xmin, ymin))

            polygon = arcpy.Polygon(arr, sr)

            # =========================
            # CLEAR + INSERT (UPDATE MODE)
            # =========================
            with arcpy.da.UpdateCursor(output_fc, ["SHAPE@"]) as cur:
                for row in cur:
                    cur.deleteRow()

            with arcpy.da.InsertCursor(output_fc, ["SHAPE@"]) as cur:
                cur.insertRow([polygon])

            # =========================
            # REPAIR
            # =========================
            arcpy.RepairGeometry_management(output_fc)

            # =========================
            # VALIDASI
            # =========================
            desc = arcpy.Describe(output_fc)

            if not desc.hasZ or not desc.hasM:
                raise Exception("Z/M tidak aktif")

            arcpy.AddMessage("✅ SUCCESS - SIAP UNTILITY NETWORK")

        except Exception as e:
            arcpy.AddError(f"❌ ERROR: {str(e)}")

            # =========================
            # DEBUG OUTPUT
            # =========================
            arcpy.AddMessage(f"📍 Output path: {output_fc}")

            # =========================
            # REFRESH CATALOG
            # =========================
            arcpy.RefreshCatalog(os.path.dirname(target_fd))

            # =========================
            # ADD TO MAP
            # =========================
            try:
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                m = aprx.activeMap
                if m:
                    m.addDataFromPath(output_fc)
                    arcpy.AddMessage("🗺 Layer ditambahkan ke map")
            except:
                arcpy.AddWarning("⚠ Tidak bisa add ke map (abaikan)")