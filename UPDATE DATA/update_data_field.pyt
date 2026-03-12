import arcpy

def normalize_guid(val):
    if not val:
        return None
    return str(val).strip("{}").upper()


class Toolbox(object):
    def __init__(self):
        self.label = "Data Update Toolbox"
        self.alias = "phototools"
        self.tools = [UpdatePhoto]


class UpdatePhoto(object):

    def __init__(self):
        self.label = "Update Data From Table"
        self.description = "Update field dari tabel sumber"
        self.canRunInBackground = False


    def getParameterInfo(self):

        param0 = arcpy.Parameter(
            displayName="Layer Sumber",
            name="layerA",
            datatype="GPTableView",
            parameterType="Required",
            direction="Input"
        )

        param1 = arcpy.Parameter(
            displayName="Layer Target",
            name="layerB",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        param2 = arcpy.Parameter(
            displayName="Field ID Sumber",
            name="fieldA",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        param2.parameterDependencies = ["layerA"]
        param2.enabled = False

        param3 = arcpy.Parameter(
            displayName="Field ID Target",
            name="fieldB",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        param3.parameterDependencies = ["layerB"]
        param3.enabled = False

        param4 = arcpy.Parameter(
            displayName="Field Sumber",
            name="filelink",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        param4.parameterDependencies = ["layerA"]
        param4.enabled = False

        param5 = arcpy.Parameter(
            displayName="Field Target",
            name="photofield",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        param5.parameterDependencies = ["layerB"]
        param5.enabled = False

        param6 = arcpy.Parameter(
            displayName="Mode Update",
            name="mode",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        param6.filter.type = "ValueList"
        param6.filter.list = ["UPDATE_EXISTING","SKIP_EXISTING"]
        param6.value = "SKIP_EXISTING"

        return [param0,param1,param2,param3,param4,param5,param6]


    def updateParameters(self, parameters):

        if parameters[0].value:
            parameters[2].enabled = True
        else:
            parameters[2].enabled = False

        if parameters[1].value:
            parameters[3].enabled = True
        else:
            parameters[3].enabled = False

        if parameters[2].value:
            parameters[4].enabled = True
        else:
            parameters[4].enabled = False

        if parameters[3].value:
            parameters[5].enabled = True
        else:
            parameters[5].enabled = False


    def execute(self, parameters, messages):

        layerA = parameters[0].valueAsText
        layerB = parameters[1].valueAsText
        fieldA = parameters[2].valueAsText
        fieldB = parameters[3].valueAsText
        filelink = parameters[4].valueAsText
        photofield = parameters[5].valueAsText
        mode = parameters[6].valueAsText

        mapping = {}

        arcpy.AddMessage("Membaca data sumber...")

        with arcpy.da.SearchCursor(layerA,[fieldA,filelink]) as cursorA:
            for g,p in cursorA:

                g_norm = normalize_guid(g)

                if g_norm and p:
                    mapping[g_norm] = p

        arcpy.AddMessage("Total key: {}".format(len(mapping)))

        count_process = 0
        count_update = 0

        with arcpy.da.UpdateCursor(layerB,[fieldB,photofield]) as cursorB:

            for row in cursorB:

                g = row[0]
                photo = row[1]

                count_process += 1

                if mode == "SKIP_EXISTING":
                    if photo not in (None,""," "):
                        continue

                g_norm = normalize_guid(g)

                if g_norm in mapping:
                    row[1] = mapping[g_norm]
                    cursorB.updateRow(row)
                    count_update += 1

        arcpy.AddMessage("Total diproses: {}".format(count_process))
        arcpy.AddMessage("Total update: {}".format(count_update))