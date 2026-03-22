import arcpy
import os

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
            arcpy.AddMessage(f"🔧 Edit ON: {self.workspace}")

            if not os.path.exists(self.workspace):
                raise Exception(f"Workspace invalid: {self.workspace}")

            self.editor = arcpy.da.Editor(self.workspace)
            self.editor.startEditing(False, True)
            self.editor.startOperation()
        else:
            arcpy.AddMessage("⚡ No edit session")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if self.editor:
            if exc_type:
                self.editor.stopOperation()
                self.editor.stopEditing(False)
                arcpy.AddError("❌ Rollback")
            else:
                self.editor.stopOperation()
                self.editor.stopEditing(True)
                arcpy.AddMessage("✅ Saved")


def is_utility_network(network):
    try:
        return arcpy.Describe(network).datasetType == "UtilityNetwork"
    except:
        return False


def do_trace(start_layer, network):

    if is_utility_network(network):

        arcpy.AddMessage("▶ Utility Network Trace")

        arcpy.un.Trace(
            in_utility_network=network,
            trace_type="DOWNSTREAM",
            starting_points=start_layer,
            result_types=["SELECTION"]
        )

        return start_layer

    else:
        raise Exception(
            "Geometric Network tidak didukung di ArcGIS Pro v3. Gunakan Utility Network."
        )


def update_field(layer, field, value):

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


class BaseTraceTool(object):

    def updateMessages(self, parameters):

        mode = parameters[5].valueAsText
        network = parameters[0].valueAsText

        if mode == "DOWNSTREAM_TRACE" and not network:
            parameters[0].setErrorMessage("Network wajib diisi untuk mode trace")

        return

    def updateParameters(self, parameters):

        mode = parameters[5].valueAsText

        if mode == "UPDATE_WITHOUT_NETWORK":
            parameters[0].enabled = False   # Network disable
            parameters[0].value = None
        else:
            parameters[0].enabled = True    # Network aktif

        return

    def get_params(self):

        p1 = arcpy.Parameter(
            displayName="Network",
            name="network",
            datatype="DEFeatureDataset",
            parameterType="Optional",
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


    def run(self, parameters):

        network = parameters[0].valueAsText
        source = parameters[1].valueAsText
        source_field = parameters[2].valueAsText
        targets = parameters[3].valueAsText.split(";")
        target_field = parameters[4].valueAsText
        mode = parameters[5].valueAsText

        total = int(arcpy.management.GetCount(source)[0])
        arcpy.SetProgressor("step", "Processing...", 0, total, 1)

        arcpy.AddMessage(f"MODE: {mode}")

        with SafeEditor(source):

            if mode == "UPDATE_WITHOUT_NETWORK":
                arcpy.AddMessage("⚡ Update tanpa network")
                with arcpy.da.SearchCursor(source, ["OID@", source_field]) as cursor:

                    for i, (oid, value) in enumerate(cursor, 1):

                        arcpy.SetProgressorPosition(i)
                        for lyr in targets:
                            try:
                                selected_count = int(arcpy.management.GetCount(source)[0])

                                if selected_count > 0:

                                    arcpy.management.SelectLayerByAttribute(
                                        lyr,
                                        "NEW_SELECTION",
                                        f"{target_field} IS NOT NULL OR {target_field} IS NULL"
                                    )
                                else:
                                    arcpy.management.SelectLayerByAttribute(lyr, "CLEAR_SELECTION")

                                updated = update_field(lyr, target_field, value)
                                arcpy.AddMessage(f"✔ {lyr}: {updated}")
                            except Exception as e:
                                arcpy.AddWarning(f"Skip {lyr}: {str(e)}")


            else:
                arcpy.AddMessage("🔴 Downstream Trace aktif")
                with arcpy.da.SearchCursor(source, ["OID@", source_field]) as cursor:

                    for i, (oid, value) in enumerate(cursor, 1):

                        arcpy.SetProgressorPosition(i)
                        arcpy.management.SelectLayerByAttribute(
                            source, "NEW_SELECTION", f"OBJECTID = {oid}"
                        )

                        trace_layer = do_trace(source, network)
                        for lyr in targets:
                            try:
                                arcpy.management.SelectLayerByLocation(
                                    lyr,
                                    "INTERSECT",
                                    trace_layer,
                                    selection_type="NEW_SELECTION"
                                )

                                selected_count = int(arcpy.management.GetCount(source)[0])

                                if selected_count > 0:

                                    arcpy.management.SelectLayerByAttribute(
                                        lyr,
                                        "NEW_SELECTION",
                                        f"{target_field} IS NOT NULL OR {target_field} IS NULL"
                                    )
                                else:
                                    arcpy.management.SelectLayerByAttribute(lyr, "CLEAR_SELECTION")

                                updated = update_field(lyr, target_field, value)
                                arcpy.AddMessage(f"✔ {lyr}: {updated}")

                            except Exception as e:
                                arcpy.AddWarning(f"Skip {lyr}: {str(e)}")

        arcpy.ResetProgressor()

        
class GenerateSUTM(object):

    def __init__(self):
        self.label = "Generate SUTM"
        self.description = "Auto X/Y Start-End"

    def getParameterInfo(self):

        param = arcpy.Parameter(
            displayName="Layer",
            name="layer",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        return [param]

    def execute(self, parameters, messages):

        layer = parameters[0].valueAsText
        fields = ["X_Start", "Y_Start", "X_End", "Y_End"]

        for f in fields:
            if f not in [fld.name for fld in arcpy.ListFields(layer)]:
                arcpy.AddField_management(layer, f, "DOUBLE")

        total = int(arcpy.management.GetCount(layer)[0])
        selected = int(arcpy.management.GetCount(layer)[0])

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


class GenerateGardu(BaseTraceTool):
    def __init__(self):
        self.label = "Generate Gardu"
        self.description = "GarduDistribusi → downstream"

    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters)


class GeneratePenyulang(BaseTraceTool):
    def __init__(self):
        self.label = "Generate Penyulang"
        self.description = "MVCABLE → downstream"

    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters)


class GenerateGI(BaseTraceTool):
    def __init__(self):
        self.label = "Generate GI"
        self.description = "TRAFOGI → downstream"

    def getParameterInfo(self):
        return self.get_params()

    def execute(self, parameters, messages):
        self.run(parameters) 