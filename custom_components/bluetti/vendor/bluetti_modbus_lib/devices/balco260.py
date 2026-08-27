from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, field

# GENERATED FILE! DO NOT EDIT!


class Balco260(BluettiDevice):
    d_num_inverters = field(
        t=FieldType.UINT16,
        address=50001,
    )
    ac_o_p_total = field(
        t=FieldType.UINT16,
        address=50002,
        unit="W",
    )
    pv_i_p_total = field(
        t=FieldType.UINT16,
        address=50004,
        unit="W",
    )
    g_i_p_total = field(
        t=FieldType.UINT16,
        address=50006,
        unit="W",
    )
    d_inverter_total = field(
        t=FieldType.UINT16,
        address=50008,
        unit="W",
    )
    pv_ac_p = field(
        t=FieldType.UINT16,
        address=50010,
        unit="W",
    )
    ac_o_e_total = field(
        t=FieldType.UINT16,
        address=50012,
        unit="kWh",
        scale=0.1,
    )
    pv_i_e_total = field(
        t=FieldType.UINT16,
        address=50014,
        unit="kWh",
        scale=0.1,
    )
    g_i_e_total = field(
        t=FieldType.UINT16,
        address=50016,
        unit="kWh",
        scale=0.1,
    )
    g_o_e_total = field(
        t=FieldType.UINT16,
        address=50018,
        unit="kWh",
        scale=0.1,
    )
    pv_ac_e = field(
        t=FieldType.UINT16,
        address=50020,
        unit="kWh",
        scale=0.1,
    )
    d_inverter_status = field(
        t=FieldType.ENUM,
        address=50022,
        enum_type=InverterStatus,
    )
    d_inverter_warning = field(
        t=FieldType.ENUM,
        address=50023,
        count=4,
        enum_type=InverterWarning,
    )
    d_inverter_fault = field(
        t=FieldType.ENUM,
        address=50027,
        count=5,
        enum_type=InverterFault,
    )
    d_inverter_type = field(
        t=FieldType.STRING,
        address=50200,
        length=6,
    )
    g_i_f = field(
        t=FieldType.UINT16,
        address=50214,
        unit="Hz",
        scale=0.1,
    )
    pv_1_i_p = field(
        t=FieldType.UINT16,
        address=50269,
        unit="W",
    )
    pv_1_i_v = field(
        t=FieldType.UINT16,
        address=50270,
        unit="V",
        scale=0.1,
    )
    pv_1_i_c = field(
        t=FieldType.UINT16,
        address=50271,
        unit="A",
        scale=0.1,
    )
    pv_2_i_p = field(
        t=FieldType.UINT16,
        address=50273,
        unit="W",
    )
    pv_2_i_v = field(
        t=FieldType.UINT16,
        address=50274,
        unit="V",
        scale=0.1,
    )
    pv_2_i_c = field(
        t=FieldType.UINT16,
        address=50275,
        unit="A",
        scale=0.1,
    )
    pv_3_i_p = field(
        t=FieldType.UINT16,
        address=50277,
        unit="W",
    )
    pv_3_i_v = field(
        t=FieldType.UINT16,
        address=50278,
        unit="V",
        scale=0.1,
    )
    pv_3_i_c = field(
        t=FieldType.UINT16,
        address=50279,
        unit="A",
        scale=0.1,
    )
    pv_4_i_p = field(
        t=FieldType.UINT16,
        address=50281,
        unit="W",
    )
    pv_4_i_v = field(
        t=FieldType.UINT16,
        address=50282,
        unit="V",
        scale=0.1,
    )
    pv_4_i_c = field(
        t=FieldType.UINT16,
        address=50283,
        unit="A",
        scale=0.1,
    )
    d_num_battery_packs = field(
        t=FieldType.UINT16,
        address=51001,
    )
    b_v_total = field(
        t=FieldType.UINT16,
        address=51002,
        unit="V",
        scale=0.1,
    )
    b_c_total = field(
        t=FieldType.UINT16,
        address=51003,
        unit="A",
        scale=0.1,
    )
    b_soc_total = field(
        t=FieldType.UINT16,
        address=51004,
        unit="%",
    )
    b_soh_total = field(
        t=FieldType.UINT16,
        address=51005,
        unit="%",
    )
    b_type = field(
        t=FieldType.STRING,
        address=51200,
        length=6,
    )
    b_v = field(
        t=FieldType.UINT16,
        address=51219,
        unit="V",
        scale=0.1,
    )
    b_soc = field(
        t=FieldType.UINT16,
        address=51221,
        unit="%",
    )
    b_soh = field(
        t=FieldType.UINT16,
        address=51222,
        unit="%",
    )
    b_cycle_count = field(
        t=FieldType.UINT16,
        address=51223,
    )
    b_t_avg = field(
        t=FieldType.INT16,
        address=51224,
        unit="°C",
    )
    b_cell_count = field(
        t=FieldType.UINT16,
        address=51234,
    )
    b_ntc_count = field(
        t=FieldType.UINT16,
        address=51235,
    )
    b_i_e = field(
        t=FieldType.UINT32,
        address=51236,
        unit="Wh",
    )
    b_o_e = field(
        t=FieldType.UINT32,
        address=51238,
        unit="Wh",
    )
    ac_o_switch = field(
        t=FieldType.UINT16,
        address=57001,
    )
    g_i_switch = field(
        t=FieldType.UINT16,
        address=57009,
    )
    g_o_switch = field(
        t=FieldType.UINT16,
        address=57010,
    )
    b_soc_low = field(
        t=FieldType.UINT16,
        address=57016,
        unit="%",
    )
    b_soc_high = field(
        t=FieldType.UINT16,
        address=57017,
        unit="%",
    )
