import arcpy
import os
import datetime


LOG_FILE = os.path.join(arcpy.env.scratchFolder, "trace_log.txt")

def log(msg):
    arcpy.AddMessage(msg)
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.datetime.now()} - {msg}\n")


def is_utility_network(network_path):
    try:
        desc = arcpy.Describe(network_path)
        return desc.datasetType == "UtilityNetwork"
    except:
        return False


def do_trace(start_layer, network, trace_type="DOWNSTREAM"):
    """Support Utility Network & Non Utility"""
    result_layer = "in_memory\\trace_result"

    if is_utility_network(network):
        log("Menggunakan Utility Network Trace")
        arcpy.un.Trace(
            in_utility_network=network,
            trace_type=trace_type,
            starting_points=start_layer,
            result_types=["SELECTION"]
        )
        return start_layer
    else:
        log("Pakai Geometric Network Trace")
        arcpy.TraceGeometricNetwork_management(
            in_geometric_network=network,
            out_network_layer="trace_layer",
            in_flags=start_layer,
            trace_type="TRACE_DOWNSTREAM"
        )
        return "trace_layer"


def update_layer(layer, field, value):
    count = int(arcpy.management.GetCount(layer)[0])

    if count == 0:
        return 0

    with arcpy.da.UpdateCursor(layer, [field]) as cursor:
        for row in cursor:
            row[0] = value
            cursor.updateRow(row)

    return count


class Toolbox(object):
    def __init__(self):
        self.label = "Fieldmap Automation Tools"
        self.alias = "fieldmap"
        self.tools = [GenerateGardu, GeneratePenyulang, GenerateGI]


class BaseTraceTool(object):

    def common_parameters(self):
        params = []

        params.append(arcpy.Parameter(
            displayName="Network (Utility / Geometric)",
            name="network",
            datatype="DEFeatureDataset",
            parameterType="Required",
            direction="Input"
        ))

        params.append(arcpy.Parameter(
            displayName="Layer Sumber",
            name="source_layer",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        ))

        params.append(arcpy.Parameter(
            displayName="Field Sumber (Nama)",
            name="source_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        ))

        params.append(arcpy.Parameter(
            displayName="Layer Target (Multiple)",
            name="target_layers",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
            multiValue=True
        ))

        params.append(arcpy.Parameter(
            displayName="Field Target",
            name="target_field",
            datatype="String",
            parameterType="Required",
            direction="Input"
        ))

        return params

    def execute_main(self, parameters):
        network = parameters[0].valueAsText
        source_layer = parameters[1].valueAsText
        source_field = parameters[2].valueAsText
        target_layers = parameters[3].valueAsText.split(";")
        target_field = parameters[4].valueAsText

        total = int(arcpy.management.GetCount(source_layer)[0])

        arcpy.SetProgressor("step", "Processing...", 0, total, 1)

        log(f"TOTAL SOURCE: {total}")

        with arcpy.da.SearchCursor(source_layer, ["OID@", source_field]) as cursor:
            for i, row in enumerate(cursor, 1):

                oid = row[0]
                value = row[1]

                arcpy.SetProgressorPosition(i)
                log(f"Processing {i}/{total} → {value}")

                arcpy.management.SelectLayerByAttribute(
                    source_layer,
                    "NEW_SELECTION",
                    f"OBJECTID = {oid}"
                )

                trace_layer = do_trace(source_layer, network)

                for lyr in target_layers:
                    try:
                        arcpy.management.SelectLayerByLocation(
                            lyr,
                            "INTERSECT",
                            trace_layer,
                            selection_type="NEW_SELECTION"
                        )

                        updated = update_layer(lyr, target_field, value)

                        log(f"Update {lyr} = {updated} row")

                    except Exception as e:
                        log(f"ERROR layer {lyr}: {str(e)}")

        arcpy.ResetProgressor()
        log("SELESAI")


class GenerateGardu(BaseTraceTool):

    def __init__(self):
        self.label = "Generate Nama Gardu"
        self.description = "Update field GARDU dari GarduDistribusi"

    def getParameterInfo(self):
        return self.common_parameters()

    def execute(self, parameters, messages):
        log("GENERATE GARDU")
        self.execute_main(parameters)


class GeneratePenyulang(BaseTraceTool):

    def __init__(self):
        self.label = "Generate Nama Penyulang"
        self.description = "Update field PENYULANG dari MVCABLE"

    def getParameterInfo(self):
        return self.common_parameters()

    def execute(self, parameters, messages):
        log("GENERATE PENYULANG")
        self.execute_main(parameters)


class GenerateGI(BaseTraceTool):

    def __init__(self):
        self.label = "Generate KODE GI"
        self.description = "Update field KODE_GI dari TRAFOGI"

    def getParameterInfo(self):
        return self.common_parameters()

    def execute(self, parameters, messages):
        log("GENERATE GI")
        self.execute_main(parameters)