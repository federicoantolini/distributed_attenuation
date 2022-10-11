import os
import math
import numpy as np
import pandas as pd
import geopandas as gpd




def find_nearest(array, value):
    '''
    returns the element in array closest in value to value
    '''
    array = np.asarray(array)
    value_arr = np.full(shape=np.shape(array), fill_value=value)
    idx = (np.abs(array - value_arr)).argmin()
    return array[idx]


def calc_B_rect_orif(row):
    '''
    calculates orifice width based on the length of the dam and the width of the channel
    '''
    length = min(row['reachWid'], row['damLength'])
    B_rect_orif = min(0.2*length, 5)
    B_rect_orif = round(round (B_rect_orif/0.05) * 0.05, 2)
    return B_rect_orif

def calc_H_rect_orif(row):
    '''
    calculates orifice height based on orifice width and the height of the dam
    '''
    height = row['maxH']
    B_orif = row['B_orif']
    if height < 3:
        H_rect_orif = min (0.5*B_orif, 0.2*height)
    else:
        H_rect_orif = min (0.5*B_orif, 0.3*height, 2)
    H_rect_orif = round(round (H_rect_orif/0.05) * 0.05, 2)
    return H_rect_orif

def calc_D_equiv(row, commercial_D_list):
    '''
    calculates the nearest commercial diameter to the orifice height
    '''
    H_orif = row['H_orif']
    H_orif_inches = H_orif * 39.3701
    commercial_D_equiv = find_nearest(commercial_D_list, H_orif_inches)
    return commercial_D_equiv

def calc_num_pipes(row):
    '''
    calculates the number of commercial pipes so that the sum of orifice sections is equivalent to the rectangular orifice section
    max 10 pipes
    '''
    rect_orif_area = row["rect_orif_area"]
    single_circ_orif_area = row["single_circ_orif_area"]
    num_of_pipes = round(rect_orif_area / single_circ_orif_area)
    if num_of_pipes > 10:
        num_of_pipes = 10
    return num_of_pipes


def calc_top_width(row):
    '''
    calculates the top width of the dam section
    '''
    length = min(row['reachWid'], row['damLength'])
    height = row['maxH']
    # top_width = max(math.ceil(length/5), 3)    # controlla  min 10 feet
    # from design small dams 1987 + additional width proportional to dam length, which varies from Strahler 2 to 6!
    top_width_unrounded = height*(3.28/5) + length/5
    top_width = max(2, round( round(top_width_unrounded/0.5) * 0.5, 1 ) )   
    # agree with small dams projects on Clear Creek, IA
    # according to 356_IA_CPS_Dike_2015.pdf, top width = 10-12 feet = 3-4 meters 
    return top_width

def calc_base_width(row, us_slope, ds_slope):
    '''
    calculates the bottom width of the dam section
    '''
    # upstream_slope = 3
    # downstream_slope = 3
    height = row['maxH']
    top_width = row["top_width"]
    base_width = top_width + us_slope*height + ds_slope*height
    return base_width


def calc_damBody_volume(row):
    '''
    calculates the volume of the dam body in correspondence of the channel (between the banks)
    '''
    length = min(row['reachWid'], row['damLength'])
    height = row['maxH']
    top_width = row["top_width"]
    base_width = row["base_width"]
    cross_section_area = 0.5 * (top_width + base_width) * height
    volume = cross_section_area * length
    return volume

def calc_damSide_volume(row):
    '''
    calculates the volume of the dam body beyond the channel banks
    conventional geometry, triangle made of 1.dam height, 2. length of dam beyond channel bank, and 
    3.line connecting dam bottom at the bank and end of damLength
    '''
    damBody_Length = min(row['reachWid'], row['damLength'])
    damLength = row['damLength']
    height = row['maxH']
    base_width = row['base_width']
    top_width = row["top_width"]
    side_volume = (top_width+base_width) * height * (damLength-damBody_Length) / 4
    return side_volume

def calc_damBody_surface(row, us_slope, ds_slope):
    '''
    calculates the surface of the dam body in correspondence of the channel (between the banks)
    '''
    length = min(row['reachWid'], row['damLength'])
    height = row['maxH']
    top_width = row["top_width"]
    us_surface_area = length * (height * math.sqrt(us_slope**2 + 1))
    ds_surface_area = length * (height * math.sqrt(ds_slope**2 + 1))
    top_surface_area = length * top_width
    surface_area = us_surface_area + ds_surface_area + top_surface_area
    return surface_area

def calc_damSide_surface(row, us_slope, ds_slope):
    '''
    calculates the surface of the dam body beyond the channel banks
    '''
    damBody_Length = min(row['reachWid'], row['damLength'])
    damLength = row['damLength']
    height = row['maxH']
    top_width = row["top_width"]
    us_surface_area = (height * math.sqrt(us_slope**2 + 1)) * (damLength-damBody_Length) / 2
    ds_surface_area = (height * math.sqrt(ds_slope**2 + 1)) * (damLength-damBody_Length) / 2
    top_surface_area = top_width * (damLength-damBody_Length)
    surface_area = us_surface_area + ds_surface_area + top_surface_area
    return surface_area


def calc_pipe_meter_cost(row):
    '''
    calculates the cost of pipes using pipe cost per meter
    '''
    base_width = row["base_width"]
    commercial_D = row["D_orif_inches"]
    num_pipes = row["num_pipes"]
    cost_per_meter = pipe_cost_meter_dict[commercial_D][0]/pipe_cost_meter_dict[commercial_D][1]
    pipe_cost = num_pipes * base_width * cost_per_meter
    return pipe_cost

def calc_pipe_feet_cost(row):
    '''
    calculates the cost of pipes using pipe cost per feet
    '''
    base_width_feet = row["base_width_feet"]
    commercial_D = row['D_orif_inches']
    num_pipes = row["num_pipes"]
    cost_per_feet = pipe_cost_feet_dict[commercial_D][0]/pipe_cost_feet_dict[commercial_D][1]
    pipe_cost = num_pipes * base_width_feet * cost_per_feet
    return pipe_cost

def interpol_pipe_cost(row, b=1.4266, m=170.02):
    '''
    calculates the interpolated cost of pipes
    '''
    base_width_feet = row["base_width_feet"]
    rect_orif_area = row["rect_orif_area"]
    cost_per_feet = b + m*rect_orif_area
    pipe_cost = base_width_feet * cost_per_feet
    return pipe_cost
    



pipe_cost_feet_dict = { 
    # internal diameter in inches : [US$, length in feet]
    4.0 : [2, 20, 0.00811],    # 1.8
    6.0 : [3.5, 20, 0.01824],    # 3.5
    8.0 : [5.5, 1, 0.03243],    # 12.57
    10.0 : [8, 1, 0.05067],   # 15.90
    12.0 : [11.5, 1, 0.07297],   # 22.37
    15.0 : [20, 1, 0.11401],   #
    18.0 : [29, 1, 0.16417],
    24.0 : [58, 1, 0.29186],
    30.0 : [88, 1, 0.45604],
    36.0 : [120.5, 1, 0.65699],
    42.0 : [155.5, 1, 0.89383],
    48.0 : [193.5, 1, 1.16745], 
}


pipe_cost_meter_dict = { 
    # internal diameter in inches : [US$, length in meters, area in sq meters]
    4.0 : [7, 1, 0.00811],    # 1.8
    6.0 : [12, 1, 0.01824],    # 3.5
    8.0 : [18, 1, 0.03243],    # 12.57
    10.0 : [26, 1, 0.05067],   # 15.90
    12.0 : [38, 1, 0.07297],   # 22.37
    15.0 : [65, 1, 0.11401],   #
    18.0 : [95, 1, 0.16417],
    24.0 : [190, 1, 0.29186],
    30.0 : [290, 1, 0.45604],
    36.0 : [395, 1, 0.65699],
    42.0 : [510, 1, 0.89383],
    48.0 : [635, 1, 1.16745], 
}

# https://www.brazoriacountytx.gov/home/showpublisheddocument/11927/637249782901700000
# bids
# 18" HDPE PIPE .16417 m2    $ 8.22 / feet   $ 9.57 / feet    avg $ 8.61 / feet 
# 24" HDPE PIPE .29186 m2    $14.16 / feet   $16.49 / feet    avg $14.79 / feet
# 30" HDPE PIPE .45604 m2    $19.32 / feet   $22.49 / feet    avg $20.12 / feet
# 36" HDPE PIPE .65699 m2    $25.72 / feet   $29.94 / feet    avg $26.79 / feet
# 42" HDPE PIPE .89383 m2    $36.75 / feet   $42.78 / feet    avg $38.22 / feet
# 48" HDPE PIPE 1.16745 m2   $42.12 / feet   $49.04 / feet    avg $43.77 / feet
# 60" HDPE PIPE 1.82415 m2   $72.00 / feet   $83.81 / feet    avg $74.80 / feet


# https://www.fairfaxcounty.gov/landdevelopment/sites/landdevelopment/files/assets/documents/pdf/publications/unit-price-schedule.pdf
# 2021 Unit Price Schedule, Land Development Services, Fairfax Co, VA
# 6" - 12" HDPE:  $ 51 / feet
# 15"- 30" HDPE:  $117 / feet
# 36"- 48" HDPE:  $193 / feet
# 60"      HDPE:  $289 / feet

# Single Box Culvert, 4'x4'  1.48645 m2  : $ 438 / feet
# Single Box Culvert, 5'x5'  2.32258 m2  : $ 535 / feet
# Single Box Culvert, 6'x6' : $ 652 / feet
# Single Box Culvert, 8'x8' : $ 898 / feet
# Single Box Culvert, 10'x10' : $1102 / feet


# https://www.cityofchesapeake.net/Assets/documents/departments/development_permits/pfm/volumei/appendices/26-UnitPrice-List.pdf
# updated May 2019
# 8" HDPE : $ 25 / feet
# 10" HDPE: $ 28 / feet 
# 12" HDPE: $ 30 / feet 
# 15" HDPE: $ 32 / feet 
# 18" HDPE: $ 37 / feet 
# 21" HDPE: $ 45 / feet 
# 24" HDPE: $ 52 / feet 
# 27" HDPE: $ 63 / feet 
# 30" HDPE: $ 70 / feet 
# 36" HDPE: $ 90 / feet 
# 42" HDPE: $105 / feet 
# 48" HDPE: $110 / feet 

# BOX CULVERT 3'x5'  1.39355 m2  : $ 750 / feet
# BOX CULVERT 4'x5'  1.85806 m2  : $ 800 / feet
# BOX CULVERT 4'x6'  2.22967 m2  : $ 850 / feet
# BOX CULVERT 4'x7'  2.60129 m2  : $ 900 / feet
# BOX CULVERT 4'x10' 3.71612 m2  : $1100 / feet
# BOX CULVERT 5'x5'  2.32258 m2  : $ 850 / feet


# https://www.boxculvert.com/page/
# BOX CULVERT 4'x4'  1.48645 m2  : $ 345 / feet
# BOX CULVERT 5'x5'  2.32258 m2  : $ 415 / feet
# BOX CULVERT 4'x6'  2.22967 m2  : $ 415 / feet



us_slope = 3
ds_slope = 3

reservoir_shp_filename = os.path.join("reservoir_locations", "dam_design", "reservoirPolygon2.0_by_Vmax_to_damLength_w_DistToOutlet.shp")
res_df = gpd.read_file(reservoir_shp_filename)
res_df["B_orif"] = res_df.apply(calc_B_rect_orif, axis=1)
res_df["H_orif"] = res_df.apply(calc_H_rect_orif, axis=1)
res_df["rect_orif_area"] = res_df["B_orif"] * res_df["H_orif"]
res_df["D_orif_inches"] = res_df.apply(calc_D_equiv, args=[list(pipe_cost_meter_dict.keys())], axis=1)
res_df["D_orif_meters"] = res_df["D_orif_inches"] * 0.0254
res_df["single_circ_orif_area"] = math.pi*(res_df["D_orif_meters"]/2)**2
res_df["num_pipes"] = res_df.apply(calc_num_pipes, axis=1)
res_df["tot_circ_orif_area"] = res_df["num_pipes"] * res_df["single_circ_orif_area"]
res_df["delta_area"] = res_df["rect_orif_area"] - res_df["tot_circ_orif_area"]
res_df["%_circ_to_rect"] = 100 * res_df["tot_circ_orif_area"] / res_df["rect_orif_area"]

res_df["top_width"] = res_df.apply(calc_top_width, axis=1)
res_df["base_width"] = res_df.apply(calc_base_width, args=[us_slope, ds_slope], axis=1)
res_df["base_width_feet"] = res_df["base_width"] * 3.28084
res_df['damBodyVolume'] = res_df.apply(calc_damBody_volume, axis=1)
res_df['damBodyVol_yds3'] = res_df['damBodyVolume'] * 1.30795
res_df['damSideVolume'] = res_df.apply(calc_damSide_volume, axis=1)
res_df['damSideVol_yds3'] = res_df['damSideVolume'] * 1.30795
res_df['side_to_body_ratio'] = res_df['damSideVolume'] / res_df['damBodyVolume']
res_df['damVolume'] = res_df['damBodyVolume'] + res_df['damSideVolume']
res_df['damVol_yds3'] = res_df['damBodyVol_yds3'] + res_df['damSideVol_yds3']
res_df['damBody_surface'] = res_df.apply(calc_damBody_surface, args=[us_slope, ds_slope], axis=1)
res_df['damSide_surface'] = res_df.apply(calc_damSide_surface, args=[us_slope, ds_slope], axis=1)
res_df['damSurface'] = res_df['damBody_surface'] + res_df['damSide_surface']


# pipe
# use function calc_pipe_meter_cost or calc_pipe_feet_cost
# res_df['D_comm_inches'] = res_df.apply(calc_D_comm, args=[list(pipe_cost_meter_dict.keys())], axis=1)
res_df['pipe_cost'] = res_df.apply(calc_pipe_meter_cost, axis=1)
res_df['interp_pipe_cost'] = res_df.apply(interpol_pipe_cost, axis=1)


# critical area planting
# 342-CriticalAreaPlanting_2019.pdf, scenario #1
# 200$ per acre   =   0.05$ per square meter
planting_cost = 0.05
res_df["planting_cost"] = res_df['damSurface'] * planting_cost

# embankment earthfill
# 356-Dike_2019.pdf
# IA356DikeFinal.xlsb, dike
# 5.06$ per cubic yard   =   6.62$ per cubic meter
earthfill_cost = 6.62
res_df["earthfill_cost"] = res_df['damVolume'] * earthfill_cost


# labor, includes manual work and heavy equipment operations
# 378-Pond_2019.pdf average of labor $ per cubic yard
labor_cost_per_yd3 = 0.60
labor_cost_per_m3 = 0.785
res_df["labor_cost"] = labor_cost_per_m3 * res_df['damVolume']


# mobilization and equipment
# 378-Pond_2019.pdf, $ per cubic yard



# total cost
res_df["total_cost"] = res_df['interp_pipe_cost'] + res_df["planting_cost"] + res_df["earthfill_cost"]


# print(res_df.head())
print()
print(res_df[res_df['Strahler'] < 7]['side_to_body_ratio'].max(), res_df[res_df['Strahler'] < 7]['side_to_body_ratio'].min())
print(res_df[res_df['Strahler'] < 6]['side_to_body_ratio'].max(), res_df[res_df['Strahler'] < 6]['side_to_body_ratio'].min())
# print(res_df[res_df['Strahler'] < 7]['damVol_yds3'].max(), res_df[res_df['Strahler'] < 7]['reachWid'].max(), res_df[res_df['Strahler'] < 7]['damLength'].max())
# print(res_df[res_df['Strahler'] < 6]['damVol_yds3'].max(), res_df[res_df['Strahler'] < 6]['reachWid'].max(), res_df[res_df['Strahler'] < 6]['damLength'].max())
# print(res_df[res_df['Strahler'] < 6]['R_inches'].max(), res_df[res_df['Strahler'] < 6]['R_inches'].min())
# print(res_df.iloc[0,50:])
res_df.to_file(os.path.join("reservoir_locations", "dam_design", "reservoirPolygon2.0_by_Vmax_to_damLength_design_cost.shp"))




