import arcpy
import os

# =========================
# HELPER
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

        if "Utility" in desc.datasetType:
            return True
    except:
        pass

    return False


class SafeEditor:
    def __init__(self, layer):
        self.workspace = get_workspace(layer)
        self.use_editor = need_edit_session(layer)
        self.editor = None

    def __enter__(self):
        if self.use_editor:
            self.editor = arcpy.da.Editor(self.workspace)
            self.editor.startEditing(False, True)
            self.editor.startOperation()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.editor:
            if exc_type:
                self.editor.stopOperation()
                self.editor.stopEditing(False)
            else:
                self.editor.stopOperation()
                self.editor.stopEditing(True)


def validate_un(path):

    if not path:
        raise Exception("Utility Network kosong")

    if not arcpy.Exists(path):
        raise Exception(f"Utility Network tidak ditemukan: {path}")

    desc = arcpy.Describe(path)

    # 🔥 Cara aman deteksi Utility Network
    if hasattr(desc, "dataType"):
        if "UtilityNetwork" in desc.dataType:
            return True

    # 🔥 fallback (ArcGIS kadang kirim layer)
    if hasattr(desc, "catalogPath"):
        if "UtilityNetwork" in desc.catalogPath:
            return True

    # 🔥 fallback terakhir (layer dari map)
    if hasattr(desc, "name"):
        if "UtilityNetwork" in desc.name:
            return True

    raise Exception("Input bukan Utility Network (pastikan pilih dari layer Utility Network di Catalog)")


def do_trace(source, utility_network):

    validate_un(utility_network)

    arcpy.AddMessage("🔎 Menjalankan Trace...")

    result = arcpy.un.Trace(
        in_utility_network=utility_network,  # 🔥 object, bukan string
        trace_type="DOWNSTREAM",
        starting_points=source,
        result_types="SELECTION"
    )

    return result


# =========================
# UPDATE (SELECTED ONLY)
# =========================
def update_field(layer, field, value):

    count = 0

    with arcpy.da.UpdateCursor(layer, [field]) as cursor:
        for row in cursor:
            row[0] = value
            cursor.updateRow(row)
            count += 1

    return count


# =========================
# TOOLBOX
# =========================
class Toolbox(object):
    def __init__(self):
        self.label = "Fieldmap PRO Tools"
        self.alias = "fieldmap_pro"
        self.tools = [
            GenerateGardu,
            GeneratePenyulang,
            GenerateGI
        ]


# =========================
# BASE TOOL
# =========================
class BaseTraceTool(object):

    def get_params(self):

        p1 = arcpy.Parameter(
            displayName="Utility Network",
            name="utility_network",
            datatype="GPUtilityNetworkLayer",
            parameterType="Required",
            direction="Input"
        )

        p2 = arcpy.Parameter(
            displayName="Source Layer",
            name="source",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        p3 = arcpy.Parameter(
            displayName="Source Field",
            name="source_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p3.parameterDependencies = [p2.name]

        p4 = arcpy.Parameter(
            displayName="Target Layers",
            name="targets",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )

        p5 = arcpy.Parameter(
            displayName="Target Field",
            name="target_field",
            datatype="String",
            parameterType="Required",
            direction="Input"
        )

        p6 = arcpy.Parameter(
            displayName="Mode Update",
            name="mode",
            datatype="String",
            parameterType="Required",
            direction="Input"
        )

        p6.filter.type = "ValueList"
        p6.filter.list = ["UPDATE_WITHOUT_NETWORK", "DOWNSTREAM_TRACE"]
        p6.value = "DOWNSTREAM_TRACE"

        return [p1, p2, p3, p4, p5, p6]


    # =========================
    # VALIDATION UI
    # =========================
    def updateMessages(self, parameters):

        mode = parameters[5].valueAsText
        network = parameters[0].value

        if mode == "DOWNSTREAM_TRACE":
            if not network:
                parameters[0].setErrorMessage("❌ Network wajib diisi untuk mode DOWNSTREAM_TRACE")

        return


    def updateParameters(self, parameters):

        mode = parameters[5].valueAsText

        if mode == "UPDATE_WITHOUT_NETWORK":
            parameters[0].enabled = False
            parameters[0].value = None
        else:
            parameters[0].enabled = True

        return


    # =========================
    # MAIN PROCESS
    # =========================
    def run(self, parameters):

        network = parameters[0].valueAsText
        source = parameters[1].valueAsText
        source_field = parameters[2].valueAsText
        vt = parameters[3].value

        targets = []
        for i in range(vt.rowCount):
            targets.append(vt.getValue(i, 0))
            
        target_field = parameters[4].valueAsText
        mode = parameters[5].valueAsText

        # =========================
        # VALIDASI SOURCE (WAJIB 1)
        # =========================
        desc = arcpy.Describe(source)

        if not desc.FIDSet:
            arcpy.AddError("❌ Pilih 1 feature pada SOURCE")
            return

        if len(desc.FIDSet.split(";")) > 1:
            arcpy.AddError("❌ Source hanya boleh 1 feature")
            return

        # =========================
        # AMBIL NILAI SOURCE
        # =========================
        value = None

        with arcpy.da.SearchCursor(source, [source_field]) as cursor:
            for row in cursor:
                value = row[0]
                break

        if value is None:
            arcpy.AddError("❌ Field source kosong")
            return

        arcpy.AddMessage(f"Value diambil dari source: {value}")

        total = len(targets)
        arcpy.SetProgressor("step", "Processing...", 0, total, 1)

        with SafeEditor(source):

            # =========================
            # MODE TANPA NETWORK
            # =========================
            if mode == "UPDATE_WITHOUT_NETWORK":

                for i, lyr in enumerate(targets, 1):
                    arcpy.SetProgressorPosition(i)

                    try:
                        updated = update_field(lyr, target_field, value)
                        arcpy.AddMessage(f"✔ {lyr} (selected only): {updated}")
                    except:
                        pass

            # =========================
            # MODE TRACE
            # =========================
            else:

                trace_layer = do_trace(source, network)

                for i, lyr in enumerate(targets, 1):
                    arcpy.SetProgressorPosition(i)

                    try:
                        arcpy.management.SelectLayerByLocation(
                            lyr,
                            "INTERSECT",
                            trace_layer,
                            selection_type="NEW_SELECTION"
                        )

                        updated = update_field(lyr, target_field, value)
                        arcpy.AddMessage(f"✔ {lyr} (trace): {updated}")

                    except:
                        pass

        arcpy.ResetProgressor()


# =========================
# TOOLS
# =========================
class GenerateGardu(BaseTraceTool):
    def __init__(self):
        self.label = "Generate Gardu"
        self.description = "Update Gardu ke jaringan downstream atau selected"

    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters)


class GeneratePenyulang(BaseTraceTool):
    def __init__(self):
        self.label = "Generate Penyulang"
        self.description = "Update Penyulang ke jaringan downstream atau selected"

    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters)


class GenerateGI(BaseTraceTool):
    def __init__(self):
        self.label = "Generate GI"
        self.description = "Update GI ke jaringan downstream atau selected"

    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters)