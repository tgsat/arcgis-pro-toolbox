import arcpy


def normalize_guid(val):
    if not val:
        return None
    return str(val).strip("{}").upper()


class Toolbox(object):

    def __init__(self):
        self.label = "Data Update Toolbox"
        self.alias = "updatetools"
        self.tools = [UpdatePhoto]


class UpdatePhoto(object):

    def __init__(self):
        self.label = "Update Data From Table"
        self.description = "Update field layer target berdasarkan tabel sumber menggunakan ID yang sama."
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

        param6.description = (
            "Menentukan cara update data:\n"
            "SKIP_EXISTING  : Lewati record yang sudah memiliki nilai.\n"
            "UPDATE_EXISTING: Update record walaupun sudah ada nilai."
        )

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

        arcpy.AddMessage("Total key sumber: {}".format(len(mapping)))

        total_records = int(arcpy.GetCount_management(layerB)[0])

        arcpy.SetProgressor(
            "step",
            "Memproses update data...",
            0,
            total_records,
            1
        )

        count_process = 0
        count_update = 0
        count_skip = 0

        with arcpy.da.UpdateCursor(layerB,[fieldB,photofield]) as cursorB:

            for row in cursorB:

                g = row[0]
                photo = row[1]

                count_process += 1

                g_norm = normalize_guid(g)

                if g_norm not in mapping:
                    arcpy.SetProgressorPosition()
                    continue

                new_value = mapping[g_norm]

                if mode == "SKIP_EXISTING":

                    if photo not in (None,""," "):
                        count_skip += 1
                        arcpy.SetProgressorPosition()
                        continue

                    row[1] = new_value
                    cursorB.updateRow(row)
                    count_update += 1

                elif mode == "UPDATE_EXISTING":

                    if photo != new_value:
                        row[1] = new_value
                        cursorB.updateRow(row)
                        count_update += 1
                    else:
                        count_skip += 1

                arcpy.SetProgressorPosition()

        arcpy.ResetProgressor()
        arcpy.AddMessage("Proses selesai")
        arcpy.AddMessage("Total diproses : {}".format(count_process))
        arcpy.AddMessage("Total update   : {}".format(count_update))
        arcpy.AddMessage("Total skip     : {}".format(count_skip))