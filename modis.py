import os
import sys
# import pyresample
from typing import List

import numpy as np
from pyhdf.SD import SD, SDC


class ExtractSDSDataArr(object):
    """Extract data array from SDS with ignore value given"""

    def __init__(self, SD, sds_name, background_value,):
        """A"""
        self.SD = SD
        self.SDS = self._get_SDS(sds_name)
        self.attributes = self._get_sds_attributes()
        self.background_value = background_value

    def _get_SDS(self, sds_name):
        """Get the Sub Data Set of the SD"""
        try:
            SDS = self.SD.select(sds_name)
        except:
            raise IOError('{} is not a valid sub data set name! \nUse show_SDS_names() in all cls to check all the SDS name'.format(sds_name))
        return SDS

    def _get_sds_attributes(self,):
        """Get the attributes of the SDS"""
        return self.SDS.attributes()

    def _get_data_array(self, background_value):
        """The the scaled data array by scale factor and set the background value to the fill value"""

        if type(background_value) != float:
            raise TypeError('back ground value shoud be a float value!')

        data_arr = self.SDS.get()
        fill_values = self.attributes['_FillValue']

        if 'scale_factor' in self.attributes.keys():
            data_arr = data_arr * float(self.attributes['scale_factor'])
            fill_values = data_arr * float(self.attributes['scale_factor'])

        if ('reflectance_scales' in self.attributes.keys()) and ('reflectance_offsets' in self.attributes.keys()):
            # If the its Modis 021KM reflecance data, then the gains and offsets should be obtained.
            # The fill value of reflectance will be reset to -10 to distinguish with the valid data
            data_arr[data_arr == fill_values] = -10
            ref_scalers = np.array(self.attributes['reflectance_scales'])[:, None, None]  # [:, 1, 1]
            ref_offsets = np.array(self.attributes['reflectance_offsets'])[:, None, None]  # [:, 1, 1]
            data_arr = (data_arr - ref_offsets) * ref_scalers
            data_arr[data_arr < 0] = background_value
        else:
            data_arr[data_arr == fill_values] = background_value
        return data_arr

    def get(self):
        """Get the valued with back ground value setted"""
        return self._get_data_array(self.background_value)

    def show_SDS_attributes(self, SDS):
        """Show the SDS attributes"""
        for sds_arr in self._get_sds_attributes().keys():
            print(sds_arr)


class MODIS021KM_L1B(object):
    """class to read MOD021KM file.
    :argument
        * ``fpath`` -- The file path of MxD021KM file.
    """

    data_version = 'C61'
    data_type = "021KM"
    level = "1B"

    def __init__(self, fpath):

        self.fpath = fpath
        if not self.is_hdf():
            raise TypeError("It's not a valid hdf4 file.")
        self.SD = self._get_SD()
        self._get_fn_info()

        self.ref_data_list = []

    def is_hdf(self):
        """Valid if the file path is the hdf"""
        return os.path.exists(self.fpath) and self.fpath.endswith('.hdf')

    def _get_SD(self):
        """Get the SD object of the input file path"""
        try:
            return SD(self.fpath, SDC.READ)
        except:
            raise IOError("It's an invalid hdf4 file, the file may be broken!")

    def _get_fn_info(self):
        """Get Infomation from the name

        Year, day of the year, month, day, hour and min will be obtained.

        """
        fn = os.path.basename(self.fpath).split('.')
        if self.data_type not in fn[0]:
            raise FileExistsError("It's not MODIS1KM data!")

        self.year = int(fn[1][1:5])
        self.doy = int(fn[1][5:])
        self.hour = int(fn[2][:2])
        self.min = int(fn[2][2:])
        self.file_version = fn[3]

        return

    def show_SD_names(self):
        """Show the sub data set names of the read SD"""
        for sds_name in self.SD.datasets().keys():
            print(sds_name)

    def load_reflectance_data(self, sb=None, background_value=-999.0):
        """Get the Top of the Atmosphere reflectance data array

        :argument
            ``sb`` -- selected bands of MODIS.
                      The type of sb is a list of str with ["1", "2", "3" ..] or a str like "1".
                      Default value of sb is None which means all the bands will be loads.
        """
        sb_dic = self.get_sdsname_index_by_band(sb)
        self.ref_data_list = []
        for sds_name in sb_dic.keys():
            data_array = ExtractSDSDataArr(self.SD, sds_name, background_value).get()
            for index in sb_dic[sds_name]:
                self.ref_data_list.append(data_array[index, :, :])
        return

    def get_sdsname_index_by_band(self, sb=None):
        """Get the sds names and the index of 3D-array"""

        ref_250m_bns = ["1", "2", ]
        ref_500m_bns = ["3", "4", "5", "6", "7", ]
        ref_1km_bns = ["8", "9", "10", "11", "12", "13lo", "13hi", "14lo", "14hi", "15", "16", "17", "18", "19", "26"]

        if sb is None:
            sb_dic = {
                'EV_250_Aggr1km_RefSB': [x for x in len(ref_250m_bns)],
                'EV_500_Aggr1km_RefSB': [x for x in len(ref_250m_bns)],
                'EV_1KM_RefSB': [x for x in len(ref_250m_bns)]
            }
            return sb_dic
        else:
            pass

        sb_dic = {
            'EV_250_Aggr1km_RefSB': [],
            'EV_500_Aggr1km_RefSB': [],
            'EV_1KM_RefSB': []
        }

        def add2_sb_dic(sb_dic, bn):
            """Add index to corresponding sds"""
            if bn in ref_250m_bns:
                index = ref_250m_bns.index(bn)
                sb_dic['EV_250_Aggr1km_RefSB'].append(index)
            elif bn in ref_500m_bns:
                index = ref_500m_bns.index(bn)
                sb_dic['EV_500_Aggr1km_RefSB'].append(index)
            elif bn in ref_1km_bns:
                index = ref_1km_bns.index(bn)
                sb_dic['EV_1KM_RefSB'].append(index)
            else:
                raise IndexError(
                    'The selected bands are not in the MODIS021KM refSB bands name. The valid bands name is {}'.format(
                        (ref_250m_bns + ref_500m_bns + ref_1km_bns)
                    )
                )

        def remove_none_sb_dic(sb_dic):
            for key in list(sb_dic.keys()):
                if len(sb_dic[key]) == 0:
                    sb_dic.pop(key)

        if type(sb) == int:
            add2_sb_dic(sb_dic, sb)
            remove_none_sb_dic(sb_dic)
            return sb_dic

        if type(sb) is list:
            for bn in sb:
                add2_sb_dic(sb_dic, bn)
            remove_none_sb_dic(sb_dic)
            return sb_dic

        return sb_dic


if __name__ == '__main__':

    # tst_file = r'D:\MyWorkSpace\Random_Tree\MODIS_machine_learning\data\MOD02\MOD021KM.A2012284.0255.061.2017339003528.hdf'
    tst_file = '/Users/aaron/Projects/MyWorkSpace/ThreePoles/data/MOD021KM.A2019013.0450.061.2019013132919.hdf'
    mod021km = MODIS021KM_L1B(tst_file)
    mod021km.load_reflectance_data(["1", "2", "3"])
    data_array = mod021km.ref_data_list

    a = 0
