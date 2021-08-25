import os, math#, string, arcpy
import numpy as np
import pandas as pd
import geopandas as gpd
#from arcpy import env


def calc_B():
    '''
    calculate chord given h
    '''


def calc_area(B, H):
    return B*H


def calc_equiv_R(row, n=2):
    '''
    calculate the radius for n circular orifices whose overall surface is equivalent area
    '''
    B = row["B"]
    H = row["H"]
    maxH = row["maxH"]
    area = B*H
    R = math.sqrt((area/n)/math.pi)
    if R > maxH*0.4:
        R = H
    return round(R, 2)


def calc_Q_openCh_circ_orif(depth, R, Hb, i, n, num_pipes, damID):
    '''
    calculate Q through a circular orifice, using Manning equation, open channel conditions
    '''

    if depth <= Hb:
        Q = 0
    else:
        sag = round(depth - Hb, 4)    # sagitta
        
        try:
            area = R**2 * math.acos((R-sag)/R) - (R-sag) * math.sqrt(2*R*sag - sag**2)
        except:
            print("{}, depth={},   R={}   , sag={}".format(damID, depth, R, sag))
            return
            
        wet_perimeter = 2 * R * math.acos((R-sag)/R)
        hydr_R = area/wet_perimeter
        Q = (1/n) * (hydr_R**(2/3)) * (i**0.5) * area
    return Q*num_pipes  # multiply by number of pipes


def calc_Q_openCh_rect_orif(depth, B, i, n):
    '''
    calculate Q through a rectangular orifice, using Manning equation, open channel conditions
    '''
    h = depth   
    area = B * h
    wet_perimeter = 2*h + B
    hydr_R = area/wet_perimeter
    Q = (1/n) * (hydr_R**(2/3)) * (i**0.5) * area
    return Q



def calc_Q_weir_rect_orif(depth, B_orif, Hb, g):
    '''
    treting the unsubmerged upstream orifice as a broad_crested weir
    critical h above the weir is 2/3*H, H being water height measured from orifice bottom edge
    for a rectangular weir the formula for Q is simple
    '''
    if depth - Hb <= 0:
        return 0
    Cd = 0.88
    h_over_hplusP = (depth-Hb)/(depth)
    # h_over_b = (depth-Hb)/5   # this is always
    if h_over_hplusP <= 0.5:
        Cd += 0
    elif h_over_hplusP <= 0.55:
        Cd += 0.01
    elif h_over_hplusP <= 0.60:
        Cd += 0.02
    elif h_over_hplusP <= 0.65:
        Cd += 0.04
    elif h_over_hplusP <= 0.70:
        Cd += 0.05
    elif h_over_hplusP <= 0.75:
        Cd += 0.06
    elif h_over_hplusP <= 0.8:
        Cd += 0.08
    elif h_over_hplusP <= 0.85:
        Cd += 0.09
    else:
        Cd += 0.1
    
    Q = 0.385 * Cd * math.sqrt(2*g) * B_orif * (depth-Hb)**1.5
    return Q


def calc_Q_weir_circ_orif(depth, R, Hb, g, num_pipes, integr_step):
    '''
    treting the unsubmerged upstream orifice as a broad_crested weir
    critical h above the weir is 2/3*H, H being water height measured from orifice bottom edge
    for a circular weir formula is NOT simple 
    because dQ=dA*sqrt(2gh), and dA=B(h)*dh, and require integration
    the circle is instead discretized in trapezoidal stripes of dh=integr_step (1cm)
    dA(h) = 0.5* (B_below(h) + B_above(h)) * dh,  dQ = dA(h) * sqrt(2g*h)
    final Q is the sum of dQ through discretized trapezoids, multiplied by n=num of pipes
    '''
    if depth - Hb <= 0:
        return 0
    Cd = 0.88
    h_over_hplusP = (depth-Hb)/(depth)
    # h_over_b = (depth-Hb)/5   # this is always
    if h_over_hplusP <= 0.5:
        Cd += 0
    elif h_over_hplusP <= 0.55:
        Cd += 0.01
    elif h_over_hplusP <= 0.60:
        Cd += 0.02
    elif h_over_hplusP <= 0.65:
        Cd += 0.04
    elif h_over_hplusP <= 0.70:
        Cd += 0.05
    elif h_over_hplusP <= 0.75:
        Cd += 0.06
    elif h_over_hplusP <= 0.8:
        Cd += 0.08
    elif h_over_hplusP <= 0.85:
        Cd += 0.09
    else:
        Cd += 0.1

    sag = (depth-Hb)*2/3    # sagitta
    h_arr = np.arange(0, round(sag+0.001, 3), integr_step)
    h_baric_arr = (h_arr[1:] + np.roll(h_arr,1)[1:])/2
    B_arr = np.zeros(h_arr.size)
    B_arr[1:] = 2 * np.sqrt(h_arr[1:]) * np.sqrt(2*R - h_arr[1:])
    dA_arr = np.zeros(h_arr.size-1)
    dA_arr = 0.5*(B_arr[1:] + np.roll(B_arr[1:],1))*integr_step
    dQ_arr = np.zeros(dA_arr.size)
    dQ_arr = dA_arr * np.sqrt(2*g*(depth-Hb-h_baric_arr))

    Q = Cd * np.sum(dQ_arr)
    return Q*num_pipes  # multiply by number of pipes



def calc_Q_above_circ_orif(depth, R, Hb, cd, g, n, integr_step):
    '''
    calculate Q through a circular orifice, given water depth in the dam
    original formula would require an integration, as dQ = dA(h) * sqrt(2g*h)
    this is too complicated for a circular area
    the circle is instead discretized in trapezoidal stripes of dh=integr_step (1cm)
    dA(h) = 0.5* (B_below(h) + B_above(h)) * dh,  dQ = dA(h) * sqrt(2g*h)
    final Q is the sum of dQ through discretized trapezoids, multiplied by n=num of pipes
    '''
    # print("\nR = {}\n".format(R))
    k_arr = np.arange(0, round(2*R+integr_step,2), integr_step)
    # print(k_arr)
    h_arr = depth - Hb - k_arr
    # print(h_arr)
    h_baric_arr = (h_arr[1:] + np.roll(h_arr,1)[1:])/2
    B_arr = np.zeros(h_arr.size)
    B_arr[1:-1] = np.sqrt(4*(R**2 - np.power(h_arr[1:-1]-depth+Hb+R, 2)))
    # print(B_arr)
    dA_arr = np.zeros(h_arr.size)
    dA_arr[1:] = 0.5*(B_arr[1:] + np.roll(B_arr[1:],1))*integr_step
    # print(dA_arr)
    dQ_arr = np.zeros(h_arr.size)
    dQ_arr[1:] = dA_arr[1:] * np.sqrt(2*g*h_baric_arr)
    # print(dQ_arr)
    Q = cd * np.sum(dQ_arr)  # Q through single pipe

    return Q*n



def calc_Q_above_rect_orif(depth, B_orif, H_orif, cd, g):
    '''
    calculate Q through a rectangular orifice, given water depth in the dam
    '''
    Q = (2/3) * cd * math.sqrt(2*g) * B_orif * ((depth)**1.5 - (depth-H_orif)**1.5)
    return Q



def interpolate(x, x_ceil, x_floor, y_ceil, y_floor):
    '''
    interpolate the value of y between y_ceil and y_floor, given the position of x between x_ceil and x_floor
    both x and y grow monotonically (e.g. depth and storage)
    '''
    #if x_ceil == x_floor:
    #    y = y_ceil
    y = y_ceil - (x_ceil - x) * (y_ceil - y_floor) / (x_ceil - x_floor)
    return y

def create_index_ceiling(depth_array):
    index_ceil = np.zeros_like(depth_array, dtype=int)
    index_ceil[-1] = index_ceil.size-1
    use_index = -1
    for i in range (depth_array.size-2, -1, -1):
        if depth_array[i] in [0., 1., 2., 3., 4., 5., 6.]:
            index_ceil[i] = i
            use_index = i
        else:
            index_ceil[i] = use_index
    return index_ceil

def create_index_floor(depth_array):
    index_floor = np.zeros_like(depth_array, dtype=int)
    index_floor[-1] = index_floor.size-1
    use_index = 0
    for i in range (depth_array.size-1):
        if depth_array[i] in [0., 1., 2., 3., 4., 5., 6.]:
            index_floor[i] = i
            use_index = i
        else:
            index_floor[i] = use_index
    return index_floor


def build_storage_array(depth_vol_series):
    depth_array = depth_vol_series['depth']
    vol_array = depth_vol_series['volumes']
    vol_array[depth_array.size-1] = vol_array[-1]
    vol_array = vol_array[:depth_array.size]
    storage_array = np.zeros_like(depth_array)
    storage_array[-1] = vol_array[-1]

    depth_ceil = np.ceil(depth_array)
    depth_ceil[-1] = depth_array[-1]
    depth_floor = np.floor(depth_array)
    depth_floor[-1] = depth_array[-1]
    
    index_ceil = create_index_ceiling(depth_array)
    vol_ceil = np.zeros_like(depth_array)
    vol_ceil = vol_array[index_ceil]
    
    index_floor = create_index_floor(depth_array)
    vol_floor = np.zeros_like(depth_array)
    vol_floor = vol_array[index_floor]

    storage_array = np.where(depth_floor == depth_ceil,
                        vol_array,
                        interpolate(depth_array, depth_ceil, depth_floor, vol_ceil, vol_floor))
    
    return storage_array



def build_depth_array(maxh, step):
    depth_array = np.round(np.arange(0, maxh, step),1)
    depth_array = np.append(depth_array, [maxh])
    return depth_array

def build_depth_series(maxh_series, step):
    depth_series = maxh_series.apply(build_depth_array, args=[step])
    print(depth_series)
    return depth_series  


def build_storage_series(df, depth_series):
    
    local_df = pd.DataFrame(df.loc[["VOL_1", "VOL_2", "VOL_3", "VOL_4", "VOL_5", "VOLmax"]])#, "maxH"]]
    local_df = local_df.T
    vol0 = pd.Series(0, index=local_df.index, name="VOL_0")
    local_df.insert(0, vol0.name, vol0)

#     length_depth_array_series = depth_series.size
# #    max_depth_array_length = max(length_depth_array_series)
#     longest_depth_array = depth_series[length_depth_array_series.idxmax]
#     longest_depth_list = list(longest_depth_array)[:-1] + ['max']

    max_depth = depth_series.iloc[-1]
    init_vol_array = np.zeros(depth_series.size)
    storage_series = pd.Series(init_vol_array, index=depth_series.index, name="storage")
    # volumes_df = pd.DataFrame(init_vol_array, index=local_df.index)
    for i in range(0, max_depth, 1):
        storage_series[i] = local_df["VOL_{}}".format(i)]
    # volumes_series[1.0] = local_df["VOL_1"]
    # volumes_series[2.0] = local_df["VOL_2"]
    # volumes_series[3.0] = local_df["VOL_3"]
    # volumes_series[4.0] = local_df["VOL_4"]
    # volumes_series[5.0] = local_df["VOL_5"]
    storage_series[max_depth] = local_df["VOLmax"]

    
    # volume_series = volumes_df.apply(np.array, axis=1)
    depth_vol_df = pd.DataFrame({'depth':depth_series, 'storage':storage_series})
    # #return depth_vol_df
    # storage_series = depth_vol_df.apply(build_storage_array, axis=1)
    return storage_series


def create_singleRes_df(row):
    damID = row.name
    depth = row['depth']
    storage = row['storage']
    outflow = row['outflow']
    singleRes_df = pd.DataFrame({'depth':depth, 'storage':storage, 'outflow':outflow})
    singleRes_df.to_csv("./prova_optim/reservoirs1/{}_df.txt".format(damID), sep='\t')






g = 9.807         #standard gravity
cc = 0.622        #contraction coefficient
cd = 0.98       # coefficient of discharge, rounded-edged orifice; sharp-edged cd=0.6
cq = 0.385 * cd        #weir coefficient 
n_rough_corr = 0.022        # corrugated PVC/HPDE
n_rough_smooth = 0.012      # smooth walls PVC/HDPE
n_rough_streambed = 0.035   # streambed under the dam, cleaner than the rest of the streambed (0.055)

i = 0.005    # m/m slope of the pipe

Hb = 0.10         #height of the bottom of the orifice

reservoir_data_dbf = "reservoirPolygon2.0_by_Vmax_to_damLength_w_DistToOutlet.dbf"
stor_disch_folder = os.path.join("hewett_ts1min_70mm1_0mm5", "reservoirs")
huc10 = 'Volga'
huc12 = 'Hewett'
step = 0.10
integr_step = 0.01

num_pipes = 2  # number of pipes


res_df = gpd.read_file(os.path.join("reservoir_locations", reservoir_data_dbf))
res_df.set_index('damID', drop=False, inplace=True)
# print(res_df.index.tolist())
B_series = res_df["B_orif"]
H_series = res_df["H_orif"]
maxH_series = res_df["maxH"]
geometry_df = pd.DataFrame({"B":B_series, "H":H_series, "maxH":maxH_series}, index=res_df.index)
# area_series = B_series * H_series
# print(area_series.head())

R_series = geometry_df.apply(calc_equiv_R, args=[num_pipes], axis=1)
res_df["R"] = R_series

depStoOutf_all_df = pd.DataFrame(columns = ['depth','storage', 'outflow_rect', 'outflow_circ', 'damID'])

for damID in res_df.index.tolist():
# for damID in [601667]:
    # circular orifice
    R = res_df.loc[damID, "R"]
    # print(R)
    htop = round(Hb + 2*R, 2)
    circ_orif_depth_array = np.round(np.arange(0, round(htop + step,2), step), 1)
    circ_orif_depth_series = pd.Series(circ_orif_depth_array, index=circ_orif_depth_array)
    # # if damID == 200029:
    # #     print(circ_orif_depth_series)
    circ_orif_Q_series = circ_orif_depth_series.apply(calc_Q_weir_circ_orif, 
    args=[R, Hb, g, num_pipes, integr_step])

    first_depth_above = circ_orif_depth_array[-1] + step
    above_circ_orif_depth_array = np.round(np.arange(first_depth_above, res_df.loc[damID, "maxH"], step), 1)
    above_circ_orif_depth_array = np.append(above_circ_orif_depth_array, [res_df.loc[damID, "maxH"]])
    above_circ_orif_depth_series = pd.Series(above_circ_orif_depth_array, index=above_circ_orif_depth_array)
    above_circ_orif_Q_series = above_circ_orif_depth_series.apply(calc_Q_above_circ_orif, 
    args=[R, Hb, cd, g, num_pipes, integr_step])
    # # print(above_circ_orif_Q_series)
    circ_orif_concat_Q_series = circ_orif_Q_series.append(above_circ_orif_Q_series)
    # # print(circ_orif_concat_Q_series)

    # rectangular orifice
    H_orif = res_df.loc[damID, "H_orif"]
    B_orif = res_df.loc[damID, "B_orif"]
    rect_orif_depth_array = np.round(np.arange(0, Hb+H_orif+0.000001, step), 1)
    rect_orif_depth_series = pd.Series(rect_orif_depth_array, index=rect_orif_depth_array)
    rect_orif_Q_series = rect_orif_depth_series.apply(calc_Q_weir_rect_orif, 
    args=[B_orif, Hb, g])
    # print(rect_orif_Q_series)
    first_depth_above_rect = rect_orif_depth_array[-1] + step
    above_rect_orif_depth_array = np.round(np.arange(first_depth_above_rect, res_df.loc[damID, "maxH"], step), 1)
    above_rect_orif_depth_array = np.append(above_rect_orif_depth_array, [res_df.loc[damID, "maxH"]])
    above_rect_orif_depth_series = pd.Series(above_rect_orif_depth_array, index=above_rect_orif_depth_array)
    above_rect_orif_Q_series = above_rect_orif_depth_series.apply(calc_Q_above_rect_orif, 
    args=[B_orif, H_orif, cd, g])
    # print(above_rect_orif_Q_series)
    rect_orif_concat_Q_series = rect_orif_Q_series.append(above_rect_orif_Q_series)
    
    stor_out_df = pd.read_table("all_reservoirs_df_for_storage_values.txt", index_col='damID')
    # stor_out_df.drop(columns='Unnamed: 0', inplace=True)
    storage_array = stor_out_df.loc[damID, 'storage'].array
    for_storage_depth_array = build_depth_array(res_df.loc[damID, "maxH"], step)
    storage_series = pd.Series(storage_array, index=for_storage_depth_array)
    stor_out_df = None
    # stor_out_df.loc[:-1,"depth"] = stor_out_df.loc[:-1,"depth"].round(decimals=1)
    # print(stor_out_df)
    # stor_out_df.set_index("depth", inplace=True)
    # print(stor_out_df)
    
    # print(stor_out_df.index)
    # stor_out_df["outflow_circ"] = circ_orif_concat_Q_series
    # stor_out_df["outflow_rect"] = rect_orif_concat_Q_series
    # stor_out_df.drop(columns=["outflow"], inplace=True)
    # stor_out_df.to_csv(os.path.join("reservoirs", "w_circular_orifice", "{}_df.txt".format(damID)), sep='\t')
    # stor_out_df["rect_Chezy_diff"] = stor_out_df["outflow_rect"] - stor_out_df["outflow"]
    # avg_diff = stor_out_df["rect_Chezy_diff"].mean()
    # rect_Chezy_diff_dict[damID] = avg_diff

    

    # storage_series = build_storage_series(res_df.loc[damID,:], for_storage_depth_series)
    # print(damID, rect_orif_concat_Q_series)
    depStoOutf_df = pd.DataFrame({'depth':for_storage_depth_array, \
    'storage':storage_series, 
    'outflow_rect': rect_orif_concat_Q_series,
    'outflow_circ': circ_orif_concat_Q_series
    })
    depStoOutf_df.to_csv(os.path.join(stor_disch_folder, "{}_df.txt".format(damID)), sep='\t')
    
    depStoOutf_df['damID'] = damID
    depStoOutf_all_df = depStoOutf_all_df.append(depStoOutf_df, ignore_index=True)

depStoOutf_all_df.set_index(['damID', 'depth'], inplace=True)
#depStoOutf_all_df['endTerms'] = 2*depStoOutf_all_df['storage']/3600 + depStoOutf_all_df['outflow']
# print(depStoOutf_all_df.head())
depStoOutf_all_df.to_csv(os.path.join(stor_disch_folder, "all_reservoirs_df.txt"), sep='\t')
    


# res_df['rect_Chezy_diff'] = pd.Series(rect_Chezy_diff_dict)
res_df.to_file(os.path.join(stor_disch_folder, "reservoirPolygon2.0_by_Vmax_to_damLength_rect_circ.shp"), index=False)