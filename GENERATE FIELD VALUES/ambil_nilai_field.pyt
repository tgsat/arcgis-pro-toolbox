import arcpy
import os

# =========================
# UTILITAS
# =========================
def get_workspace(layer):
    desc = arcpy.Describe(layer)
    path = desc.catalogPath if hasattr(desc, "catalogPath") else layer

    while path and not (path.endswith(".gdb") or path.endswith(".sde")):
        path = os.path.dirname(path)

    return path


def need_edit_session(layer):
    try:
        desc = arcpy.Describe(layer)

        if hasattr(desc, "isVersioned") and desc.isVersioned:
            return True

        if ".sde" in desc.catalogPath.lower():
            return True

    except:
        pass

    return False


class SafeEditor:
    def __init__(self, layer):
        pass

    def __enter__(self):
        arcpy.AddMessage("⚡ Auto Edit (ArcGIS Pro)")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            arcpy.AddError("❌ Gagal update")
        else:
            arcpy.AddMessage("✅ Selesai")


def update_selected(layer, field, value):

    count = 0

    with arcpy.da.UpdateCursor(layer, [field]) as cursor:
        for row in cursor:
            row[0] = value
            cursor.updateRow(row)
            count += 1

    return count


class Toolbox(object):
    def __init__(self):
        self.label = "Fieldmap PRO Tools"
        self.alias = "fieldmap_pro"
        self.tools = [
            GenerateSUTM,
            GenerateGardu,
            GeneratePenyulang,
            GenerateGI
        ]


# =========================
# BASE SPATIAL TOOL
# =========================
class BaseTraceTool(object):

    def isLicensed(self):
        return True

    def get_params(self):

        p1 = arcpy.Parameter(
            displayName="Source Layer (Start - Trafo)",
            name="source",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        p2 = arcpy.Parameter(
            displayName="Source Field",
            name="source_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p2.parameterDependencies = [p1.name]

        p3 = arcpy.Parameter(
            displayName="Target Layers (Urut: JTR;Tiang;SR;APP)",
            name="targets",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )

        p4 = arcpy.Parameter(
            displayName="Target Field",
            name="target_field",
            datatype="String",
            parameterType="Required",
            direction="Input"
        )

        return [p1, p2, p3, p4]


    def run(self, parameters):

        source = parameters[0].valueAsText
        source_field = parameters[1].valueAsText
        targets = parameters[2].valueAsText.split(";")
        target_field = parameters[3].valueAsText

        total = int(arcpy.management.GetCount(source)[0])
        arcpy.SetProgressor("step", "Spatial Processing...", 0, total, 1)

        with SafeEditor(source):

            with arcpy.da.SearchCursor(source, ["OID@", source_field]) as cursor:

                for i, (oid, value) in enumerate(cursor, 1):

                    arcpy.SetProgressorPosition(i)

                    # 🔥 Select trafo
                    arcpy.management.SelectLayerByAttribute(
                        source, "NEW_SELECTION", f"OBJECTID = {oid}"
                    )

                    current_layer = source

                    # 🔥 CHAIN PROCESS
                    for lyr in targets:
                        try:
                            arcpy.management.SelectLayerByLocation(
                                lyr,
                                "INTERSECT",
                                current_layer,
                                selection_type="NEW_SELECTION"
                            )

                            updated = update_selected(lyr, target_field, value)

                            arcpy.AddMessage(f"✔ {lyr}: {updated}")

                            # lanjut ke layer berikutnya
                            current_layer = lyr

                        except Exception as e:
                            arcpy.AddWarning(f"Skip {lyr}: {str(e)}")

        arcpy.ResetProgressor()


# =========================
# TOOL SUTM
# =========================
class GenerateSUTM(object):

    def __init__(self):
        self.label = "Generate SUTM"
        self.description = "Auto X/Y Start-End"

    def getParameterInfo(self):
        return [
            arcpy.Parameter(
                displayName="Layer",
                name="layer",
                datatype="GPFeatureLayer",
                parameterType="Required",
                direction="Input"
            )
        ]

    def execute(self, parameters, messages):

        layer = parameters[0].valueAsText
        fields = ["X_Start", "Y_Start", "X_End", "Y_End"]

        for f in fields:
            if f not in [fld.name for fld in arcpy.ListFields(layer)]:
                arcpy.AddField_management(layer, f, "DOUBLE")

        total = int(arcpy.management.GetCount(layer)[0])
        arcpy.SetProgressor("step", "SUTM...", 0, total, 1)

        with SafeEditor(layer):

            with arcpy.da.UpdateCursor(layer, ["SHAPE@", *fields]) as cursor:

                for i, row in enumerate(cursor, 1):

                    geom = row[0]
                    if not geom:
                        continue

                    row[1] = geom.firstPoint.X
                    row[2] = geom.firstPoint.Y
                    row[3] = geom.lastPoint.X
                    row[4] = geom.lastPoint.Y

                    cursor.updateRow(row)
                    arcpy.SetProgressorPosition(i)

        arcpy.ResetProgressor()


# =========================
# IMPLEMENTASI TOOL
# =========================
class GenerateGardu(BaseTraceTool):
    def __init__(self):
        self.label = "Generate Gardu (Spatial)"
        self.description = "Trafo → downstream (Spatial)"


    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters)


class GeneratePenyulang(BaseTraceTool):
    def __init__(self):
        self.label = "Generate Penyulang (Spatial)"
        self.description = "Penyulang → downstream (Spatial)"

    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters)


class GenerateGI(BaseTraceTool):
    def __init__(self):
        self.label = "Generate GI (Spatial)"
        self.description = "GI → downstream (Spatial)"

    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters)