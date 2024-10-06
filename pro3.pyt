# -*- coding: utf-8 -*-

import arcpy


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Toolbox"
        self.alias = "SLR"

        # List of tool classes associated with this toolbox
        self.tools = [SLR]


class SLR(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "SLR operability maps"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params = [
            
            arcpy.Parameter(displayName = "Input Lidar DEM" ,
                            name = "input_dem_req", 
                            datatype = "GPLayer" , 
                            parameterType = "Required",
                            direction = "Input" ) ,
               
            arcpy.Parameter(displayName = "Input Coordinates to clip" ,
                            name = "input_clip_coordinates", 
                            datatype = "GPFeatureLayer" , #DEFeatureClass GPFeatureLayer 
                            parameterType = "Required",
                            direction = "Input" ) ,
                
            arcpy.Parameter(displayName = "Input Freeboard min requirements" ,
                            name = "input_freeboard_min_reqs", 
                            datatype = "Double" , 
                            parameterType = "Required",
                            direction = "Input" ) ,


            arcpy.Parameter(displayName = "Input Freeboard max requirements" ,
                            name = "input_freeboard_max_reqs", 
                            datatype = "Double" , 
                            parameterType = "Required",
                            direction = "Input" ) ,

            arcpy.Parameter(displayName = "Input SLR scenarios csv" ,
                            name = "input_SLR_scenarios_reqs", 
                            datatype = "GPType" , # any datatype is what gtype is
                            parameterType = "Required",
                            direction = "Input" ) ,
            
            arcpy.Parameter(displayName = "Clipped Raster Path (DO NOT CHANGE)" ,
                            name = "output_clip", 
                            datatype = "DEFeatureClass" , # this is for output of clipped raster, documentation says this datatype
                            parameterType = "Required",
                            direction = "Output" ) ,

            arcpy.Parameter(displayName = "Folder path for outputs" ,
                            name = "output", 
                            datatype = "DEFolder" , #Folder path
                            parameterType = "Required",
                            direction = "Input" ) ,
                ] 
        
        return params
    
    
        

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""

        
        input_dem_req = parameters[0].valueAsText
        input_clip_coordinates = parameters[1].value
        input_freeboard_min_reqs = parameters[2].value
        input_freeboard_max_reqs = parameters[3].value
        input_SLR_scenarios_reqs = parameters[4].valueAsText
        output_clip = parameters[5].valueAsText
        output = parameters[6].valueAsText
        


        m = arcpy.mp.ArcGISProject("CURRENT").activeMap
        print(m.name)

        in_ras = input_dem_req

        port_dem = arcpy.Raster(in_ras)
        port_dem

        
        #make polygon or rectangle an option
        #make sure to keep colors for each map the same

        arcpy.management.Clip(
            in_raster=input_dem_req,
            rectangle=input_clip_coordinates,
            out_raster=output_clip,
            in_template_dataset= input_clip_coordinates, #name of shape user makes
            nodata_value="-3.402823e+38",
            clipping_geometry="ClippingGeometry",
            maintain_clipping_extent="NO_MAINTAIN_EXTENT"
        )

        clipped_dem = arcpy.Raster(output_clip)
        clipped_dem

        m.addDataFromPath(clipped_dem)


        conversion = clipped_dem * 3.28084
        m.addDataFromPath(conversion)

        import pandas as pd
        from pandas import DataFrame

        slr_scenarios_file = input_SLR_scenarios_reqs

        slr_scenarios =pd.read_csv(slr_scenarios_file)
        #test to make sure by print
        print(slr_scenarios)

        #freeboard min and max (this is from paper but it is also an input)
        freeboard_min = input_freeboard_min_reqs
        freeboard_max = input_freeboard_max_reqs

        

        # Calculate elev_min and elev_max from raster
        elev_min = conversion.minimum
        elev_max = conversion.maximum
        #Test print
        print(elev_min)
        print(elev_max)


        #to pick the entire mean_water_lvl column 
        mean_water_lvl = slr_scenarios['Mean Water Level']
        print(mean_water_lvl)

        #operability min and max
        operability_min = mean_water_lvl + freeboard_min
        operability_max = mean_water_lvl + freeboard_max
        #Test print
        print(operability_min)
        print(operability_max)

        #mutiply by 9 so they can all have same num of row in data frame
        elev_min_values = [elev_min] * len(operability_min)
        elev_max_values = [elev_max] * len(operability_min)

        #Data frame
        df = DataFrame({
        'Year' : slr_scenarios.iloc[:9, 0].tolist(),
        'Elevation Min': elev_min_values,
        'Mean Water Level':slr_scenarios.iloc[:9, 1].tolist(),
        'Operability Min': operability_min.iloc[:9].tolist(),
        'Operability Max': operability_max.iloc[:9].tolist(),
        'Elevation Max': elev_max_values,
        })
        df

        def process_years(start_year, end_year, step, df, conversion):
            for year in range(start_year, end_year + 1, step):
                segment_years = range(year, min(year + step, end_year + 1))
                for current_year in segment_years:
                    df_year = df[df['Year'] == current_year]
                    if not df_year.empty:
                        elevation_min = df_year['Elevation Min'].iloc[0]
                        mean_water_level = df_year['Mean Water Level'].iloc[0]
                        operability_min = df_year['Operability Min'].iloc[0]
                        operability_max = df_year['Operability Max'].iloc[0]
                        elevation_max = df_year['Elevation Max'].iloc[0]
                        reclassify_matrix = [
                            [elevation_min, mean_water_level, 1],
                            [mean_water_level, operability_min, 2],
                            [operability_min, operability_max, 3],
                            [operability_max, elevation_max, 4]
                        ]
                        remapval = arcpy.sa.RemapValue(reclassify_matrix)
                        outReclass = arcpy.sa.Reclassify(
                            in_raster=conversion,
                            reclass_field="VALUE",
                            remap=remapval,
                            missing_values="DATA"
                        )
                        out_file_path = output + f"\output_reclassified_{current_year}.tif"
                        arcpy.CopyRaster_management(outReclass, out_file_path)
                    else:
                        print(f"No data available for year {current_year}.")

        # Call the function and input parameters
        process_years(2020, 2100, 10, df, conversion)
        
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
    '''
    Hex colors
    326EA0 or 45608e -blue
    B95B5B - red
    D2BC6F - yellow
    709D66 - ren
    '''
