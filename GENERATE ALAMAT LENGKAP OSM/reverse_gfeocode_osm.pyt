import arcpy
import requests
import time

class Toolbox(object):
    def __init__(self):
        self.label = "Reverse Geocode OSM"
        self.alias = "reverse_osm"
        self.tools = [ReverseGeocode]


class ReverseGeocode(object):

    def __init__(self):
        self.label = "Reverse Geocode Latitude Longitude"
        self.description = "Reverse geocode menggunakan OpenStreetMap"

    def getParameterInfo(self):

        layer = arcpy.Parameter(
            displayName="Input Layer",
            name="layer",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        lat_field = arcpy.Parameter(
            displayName="Latitude",
            name="lat_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        lat_field.parameterDependencies = [layer.name]

        lon_field = arcpy.Parameter(
            displayName="Longitude",
            name="lon_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        lon_field.parameterDependencies = [layer.name]

        address_field = arcpy.Parameter(
            displayName="Address",
            name="address_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        address_field.parameterDependencies = [layer.name]

        mode = arcpy.Parameter(
            displayName="Update Mode",
            name="mode",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        mode.filter.type = "ValueList"
        mode.filter.list = [
            "SKIP_EXISTING",
            "OVERWRITE_EXISTING"
        ]

        mode.value = "SKIP_EXISTING"

        return [layer, lat_field, lon_field, address_field, mode]

    # ====================================================
    # Reverse Geocode
    # ====================================================
    def reverse_geocode(self, lat, lon):

        if lat in (None,"",0) or lon in (None,"",0):
            return "ERROR_001: Koordinat kosong"

        try:

            url = "https://nominatim.openstreetmap.org/reverse"

            params = {
                "format":"jsonv2",
                "lat":lat,
                "lon":lon,
                "zoom":18,
                "addressdetails":1
            }

            headers = {
                "User-Agent":"ArcGISPro-Reverse-Geocode",
                "accept-language":"id"
            }

            r = requests.get(url, params=params, headers=headers, timeout=15)

            if r.status_code != 200:
                return f"ERROR_002: HTTP {r.status_code}"

            data = r.json()

            if "address" not in data:
                return "ERROR_003: Address tidak ditemukan"

            addr = data.get("address",{})

            nomor = addr.get("house_number","")

            jalan = (
                addr.get("road","") or
                addr.get("pedestrian","") or
                addr.get("footway","")
            )

            lingkungan = (
                addr.get("neighbourhood","") or
                addr.get("hamlet","")
            )

            desa = (
                addr.get("village","") or
                addr.get("suburb","") or
                addr.get("quarter","")
            )

            kecamatan = (
                addr.get("city_district","") or
                addr.get("district","")
            )

            kota = (
                addr.get("city","") or
                addr.get("town","") or
                addr.get("county","")
            )

            prov = addr.get("state","")
            kodepos = addr.get("postcode","")
            negara = addr.get("country","")

            alamat = ", ".join(
                x for x in [
                    nomor,
                    jalan,
                    lingkungan,
                    desa,
                    kecamatan,
                    kota,
                    prov,
                    kodepos,
                    negara
                ] if x
            )

            if alamat == "":
                return "ERROR_004: Alamat kosong"

            return alamat

        except requests.exceptions.Timeout:
            return "ERROR_005: Timeout server"

        except requests.exceptions.ConnectionError:
            return "ERROR_006: Koneksi internet gagal"

        except Exception as e:
            return f"ERROR_999: {str(e)}"

        finally:
            time.sleep(1)

    # ====================================================
    # EXECUTE
    # ====================================================
    def execute(self, parameters, messages):

        layer = parameters[0].valueAsText
        lat_field = parameters[1].valueAsText
        lon_field = parameters[2].valueAsText
        address_field = parameters[3].valueAsText
        mode = parameters[4].valueAsText

        total = int(arcpy.management.GetCount(layer)[0])

        arcpy.AddMessage(f"Total feature: {total}")
        arcpy.AddMessage("Memulai reverse geocode OpenStreetMap")

        arcpy.SetProgressor(
            "step",
            "Processing Reverse Geocode...",
            0,
            total,
            1
        )

        processed = 0
        skipped = 0

        with arcpy.da.UpdateCursor(layer,[lat_field,lon_field,address_field]) as cursor:

            for row in cursor:

                lat = row[0]
                lon = row[1]
                existing = row[2]

                # ===================================
                # SKIP MODE
                # ===================================
                if mode == "SKIP_EXISTING":

                    if existing not in (None,""):
                        skipped += 1
                        arcpy.SetProgressorPosition()
                        continue

                address = self.reverse_geocode(lat,lon)

                row[2] = address
                cursor.updateRow(row)

                processed += 1

                arcpy.SetProgressorPosition()

                if processed % 10 == 0:
                    arcpy.AddMessage(f"Processed {processed}/{total}")

        arcpy.ResetProgressor()

        arcpy.AddMessage(f"SELESAI")
        arcpy.AddMessage(f"Alamat diproses : {processed}")
        arcpy.AddMessage(f"Alamat dilewati : {skipped}")