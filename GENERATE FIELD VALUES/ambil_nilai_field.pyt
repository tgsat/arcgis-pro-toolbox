# -*- coding: utf-8 -*-
import arcpy
import os
import datetime

# =========================
# LOGGING
# =========================
LOG_FILE = os.path.join(arcpy.env.scratchFolder or "C:\\Temp", "fieldmap_log.txt")

def log(msg):
    arcpy.AddMessage(msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()} - {msg}\n")
    except:
        pass


# =========================
# DETECT NETWORK
# =========================
def is_utility_network(network_path):
    try:
        desc = arcpy.Describe(network_path)
        return desc.datasetType == "UtilityNetwork"
    except:
        return False


# =========================
# TRACE ENGINE
# =========================
def do_trace(start_layer, network):
    if is_utility_network(network):
        log("▶ Utility Network Trace")
        arcpy.un.Trace(
            in_utility_network=network,
            trace_type="DOWNSTREAM",
            starting_points=start_layer,
            result_types=["SELECTION"]
        )
        return start_layer
    else:
        log("▶ Geometric Network Trace")
        out_layer = "in_memory\\trace_result"
        arcpy.TraceGeometricNetwork_management(
            network,
            out_layer,
            start_layer,
            "TRACE_DOWNSTREAM"
        )
        return out_layer


# =========================
# UPDATE FIELD
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
        self.label = "Fieldmap Automation Tools"
        self.alias = "fieldmap"
        self.tools = [
            GenerateSUTM,
            GenerateGardu,
            GeneratePenyulang,
            GenerateGI
        ]


# =========================
# BASE TRACE TOOL
# =========================
class BaseTraceTool(object):

    def get_common_params(self):

        params = []

        params.append(arcpy.Parameter(
            displayName="Network",
            name="network",
            datatype="DEFeatureDataset",
            parameterType="Required",
            direction="Input"
        ))

        params.append(arcpy.Parameter(
            displayName="Source Layer",
            name="source",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        ))

        params.append(arcpy.Parameter(
            displayName="Source Field",
            name="source_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        ))

        params.append(arcpy.Parameter(
            displayName="Target Layers",
            name="targets",
            datatype="GPFeatureLayer",
            parameterType="Required",
            multiValue=True,
            direction="Input"
        ))

        params.append(arcpy.Parameter(
            displayName="Target Field",
            name="target_field",
            datatype="String",
            parameterType="Required",
            direction="Input"
        ))

        return params


    def run_trace(self, parameters):

        network = parameters[0].valueAsText
        source = parameters[1].valueAsText
        source_field = parameters[2].valueAsText
        targets = parameters[3].valueAsText.split(";")
        target_field = parameters[4].valueAsText

        total = int(arcpy.management.GetCount(source)[0])
        arcpy.SetProgressor("step", "Processing...", 0, total, 1)

        log(f"TOTAL DATA: {total}")

        with arcpy.da.SearchCursor(source, ["OID@", source_field]) as cursor:
            for i, row in enumerate(cursor, 1):

                oid, value = row

                arcpy.SetProgressorPosition(i)
                log(f"{i}/{total} → {value}")

                # Select source
                arcpy.management.SelectLayerByAttribute(
                    source, "NEW_SELECTION", f"OBJECTID = {oid}"
                )

                # Trace
                trace_layer = do_trace(source, network)

                # Update semua target
                for lyr in targets:
                    try:
                        arcpy.management.SelectLayerByLocation(
                            lyr,
                            "INTERSECT",
                            trace_layer,
                            selection_type="NEW_SELECTION"
                        )

                        updated = update_field(lyr, target_field, value)

                        log(f"✔ {lyr} updated: {updated}")

                    except Exception as e:
                        log(f"❌ ERROR {lyr}: {str(e)}")

        arcpy.ResetProgressor()
        log("SELESAI")


# =========================
# TOOL 1: SUTM
# =========================
class GenerateSUTM(object):

    def __init__(self):
        self.label = "Generate SUTM (Start-End XY)"
        self.description = "Membuat X_Start, Y_Start, X_End, Y_End dari geometry line"

    def getParameterInfo(self):

        params = []

        params.append(arcpy.Parameter(
            displayName="Layer Line (SUTM)",
            name="line_layer",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        ))

        return params


    def execute(self, parameters, messages):

        layer = parameters[0].valueAsText
        workspace = arcpy.Describe(layer).path

        fields = ["X_Start", "Y_Start", "X_End", "Y_End"]

        # Tambah field jika belum ada
        for f in fields:
            if f not in [fld.name for fld in arcpy.ListFields(layer)]:
                arcpy.AddField_management(layer, f, "DOUBLE")

        total = int(arcpy.management.GetCount(layer)[0])
        arcpy.SetProgressor("step", "Generate SUTM...", 0, total, 1)

        # =========================
        # START EDIT SESSION
        # =========================
        editor = arcpy.da.Editor(workspace)
        editor.startEditing(False, True)
        editor.startOperation()

        try:
            with arcpy.da.UpdateCursor(layer, ["SHAPE@", *fields]) as cursor:
                for i, row in enumerate(cursor, 1):

                    geom = row[0]

                    if geom is None:
                        continue

                    start = geom.firstPoint
                    end = geom.lastPoint

                    row[1] = start.X
                    row[2] = start.Y
                    row[3] = end.X
                    row[4] = end.Y

                    cursor.updateRow(row)
                    arcpy.SetProgressorPosition(i)

            editor.stopOperation()
            editor.stopEditing(True)

            log("SUTM SELESAI")

        except Exception as e:
            editor.stopOperation()
            editor.stopEditing(False)
            log(f"ERROR: {str(e)}")
            raise

        arcpy.ResetProgressor()


# =========================
# TOOL 2: GARDU
# =========================
class GenerateGardu(BaseTraceTool):

    def __init__(self):
        self.label = "Generate Nama Gardu"
        self.description = "Dari GarduDistribusi → ke semua layer downstream"

    def getParameterInfo(self):
        return self.get_common_params()

    def execute(self, parameters, messages):
        log("=== GENERATE GARDU ===")
        self.run_trace(parameters)


# =========================
# TOOL 3: PENYULANG
# =========================
class GeneratePenyulang(BaseTraceTool):

    def __init__(self):
        self.label = "Generate Nama Penyulang"
        self.description = "Dari MVCABLE → ke semua downstream"

    def getParameterInfo(self):
        return self.get_common_params()

    def execute(self, parameters, messages):
        log("=== GENERATE PENYULANG ===")
        self.run_trace(parameters)


# =========================
# TOOL 4: GI
# =========================
class GenerateGI(BaseTraceTool):

    def __init__(self):
        self.label = "Generate KODE GI"
        self.description = "Dari TRAFOGI → ke semua downstream"

    def getParameterInfo(self):
        return self.get_common_params()

    def execute(self, parameters, messages):
        log("=== GENERATE GI ===")
        self.run_trace(parameters)