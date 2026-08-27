from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, field
from ..fields.field_extras import DeviceClass, FieldCategory, FieldStateClass

# GENERATED FILE! DO NOT EDIT!


class Balco260(BluettiDevice):
    d_num_inverters = field(
        t=FieldType.UINT16,
        address=50001,
        category=FieldCategory.DIAGNOSTIC,
    )
    ac_o_p_total = field(
        t=FieldType.UINT16,
        address=50002,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    pv_i_p_total = field(
        t=FieldType.UINT16,
        address=50004,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    g_i_p_total = field(
        t=FieldType.UINT16,
        address=50006,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    d_inverter_total = field(
        t=FieldType.UINT16,
        address=50008,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    pv_ac_p = field(
        t=FieldType.UINT16,
        address=50010,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    ac_o_e_total = field(
        t=FieldType.UINT16,
        address=50012,
        unit="kWh",
        scale=0.1,
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
    )
    pv_i_e_total = field(
        t=FieldType.UINT16,
        address=50014,
        unit="kWh",
        scale=0.1,
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
    )
    g_i_e_total = field(
        t=FieldType.UINT16,
        address=50016,
        unit="kWh",
        scale=0.1,
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
    )
    g_o_e_total = field(
        t=FieldType.UINT16,
        address=50018,
        unit="kWh",
        scale=0.1,
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
    )
    pv_ac_e = field(
        t=FieldType.UINT16,
        address=50020,
        unit="kWh",
        scale=0.1,
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
    )
    d_inverter_status = field(
        t=FieldType.ENUM,
        address=50022,
        category=FieldCategory.DIAGNOSTIC,
        enum_type=InverterStatus,
    )
    d_inverter_warning = field(
        t=FieldType.ENUM,
        address=50023,
        category=FieldCategory.DIAGNOSTIC,
        count=4,
        enum_type=InverterWarning,
    )
    d_inverter_fault = field(
        t=FieldType.ENUM,
        address=50027,
        category=FieldCategory.DIAGNOSTIC,
        count=5,
        enum_type=InverterFault,
    )
    d_inverter_type = field(
        t=FieldType.STRING,
        address=50200,
        category=FieldCategory.DIAGNOSTIC,
        length=6,
    )
    g_i_f = field(
        t=FieldType.UINT16,
        address=50214,
        unit="Hz",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.FREQUENCY,
    )
    pv_1_i_p = field(
        t=FieldType.UINT16,
        address=50269,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    pv_1_i_v = field(
        t=FieldType.UINT16,
        address=50270,
        unit="V",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    pv_1_i_c = field(
        t=FieldType.UINT16,
        address=50271,
        unit="A",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    pv_2_i_p = field(
        t=FieldType.UINT16,
        address=50273,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    pv_2_i_v = field(
        t=FieldType.UINT16,
        address=50274,
        unit="V",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    pv_2_i_c = field(
        t=FieldType.UINT16,
        address=50275,
        unit="A",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    pv_3_i_p = field(
        t=FieldType.UINT16,
        address=50277,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    pv_3_i_v = field(
        t=FieldType.UINT16,
        address=50278,
        unit="V",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    pv_3_i_c = field(
        t=FieldType.UINT16,
        address=50279,
        unit="A",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    pv_4_i_p = field(
        t=FieldType.UINT16,
        address=50281,
        unit="W",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    pv_4_i_v = field(
        t=FieldType.UINT16,
        address=50282,
        unit="V",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    pv_4_i_c = field(
        t=FieldType.UINT16,
        address=50283,
        unit="A",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    d_num_battery_packs = field(
        t=FieldType.UINT16,
        address=51001,
        category=FieldCategory.DIAGNOSTIC,
    )
    b_v_total = field(
        t=FieldType.UINT16,
        address=51002,
        unit="V",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    b_c_total = field(
        t=FieldType.UINT16,
        address=51003,
        unit="A",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    b_soc_total = field(
        t=FieldType.UINT16,
        address=51004,
        unit="%",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.BATTERY,
    )
    b_soh_total = field(
        t=FieldType.UINT16,
        address=51005,
        unit="%",
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.MEASUREMENT,
    )
    b_type = field(
        t=FieldType.STRING,
        address=51200,
        category=FieldCategory.DIAGNOSTIC,
        length=6,
    )
    b_v = field(
        t=FieldType.UINT16,
        address=51219,
        unit="V",
        scale=0.1,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    b_soc = field(
        t=FieldType.UINT16,
        address=51221,
        unit="%",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.BATTERY,
    )
    b_soh = field(
        t=FieldType.UINT16,
        address=51222,
        unit="%",
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.MEASUREMENT,
    )
    b_cycle_count = field(
        t=FieldType.UINT16,
        address=51223,
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.MEASUREMENT,
    )
    b_t_avg = field(
        t=FieldType.INT16,
        address=51224,
        unit="°C",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.TEMPERATURE,
    )
    b_cell_count = field(
        t=FieldType.UINT16,
        address=51234,
        category=FieldCategory.DIAGNOSTIC,
    )
    b_ntc_count = field(
        t=FieldType.UINT16,
        address=51235,
        category=FieldCategory.DIAGNOSTIC,
    )
    b_i_e = field(
        t=FieldType.UINT32,
        address=51236,
        unit="Wh",
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
    )
    b_o_e = field(
        t=FieldType.UINT32,
        address=51238,
        unit="Wh",
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
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
        category=FieldCategory.CONFIG,
    )
    b_soc_high = field(
        t=FieldType.UINT16,
        address=57017,
        unit="%",
        category=FieldCategory.CONFIG,
    )
