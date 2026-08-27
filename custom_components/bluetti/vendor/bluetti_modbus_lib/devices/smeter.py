from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, field
from ..fields.field_extras import DeviceClass, FieldCategory, FieldStateClass

# GENERATED FILE! DO NOT EDIT!


class SMeter(BluettiDevice):
    d_status = field(
        t=FieldType.UINT16,
        address=55111,
        category=FieldCategory.DIAGNOSTIC,
    )
    d_timestamp = field(
        t=FieldType.UINT32,
        address=55112,
        category=FieldCategory.DIAGNOSTIC,
    )
    ac_a_v = field(
        t=FieldType.FLOAT32,
        address=55114,
        unit="V",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    ac_b_v = field(
        t=FieldType.FLOAT32,
        address=55116,
        unit="V",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    ac_c_v = field(
        t=FieldType.FLOAT32,
        address=55118,
        unit="V",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    ac_a_c = field(
        t=FieldType.FLOAT32,
        address=55120,
        unit="A",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    ac_b_c = field(
        t=FieldType.FLOAT32,
        address=55122,
        unit="A",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    ac_c_c = field(
        t=FieldType.FLOAT32,
        address=55124,
        unit="A",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    ac_a_p = field(
        t=FieldType.FLOAT32,
        address=55126,
        unit="kW",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    ac_b_p = field(
        t=FieldType.FLOAT32,
        address=55128,
        unit="kW",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    ac_c_p = field(
        t=FieldType.FLOAT32,
        address=55130,
        unit="kW",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    ac_a_p_reactive = field(
        t=FieldType.FLOAT32,
        address=55132,
        unit="kVAR",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_b_p_reactive = field(
        t=FieldType.FLOAT32,
        address=55134,
        unit="kVAR",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_c_p_reactive = field(
        t=FieldType.FLOAT32,
        address=55136,
        unit="kVAR",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_a_p_apparent = field(
        t=FieldType.FLOAT32,
        address=55138,
        unit="kVA",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_b_p_apparent = field(
        t=FieldType.FLOAT32,
        address=55140,
        unit="kVA",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_c_p_apparent = field(
        t=FieldType.FLOAT32,
        address=55142,
        unit="kVA",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_a_pf = field(
        t=FieldType.FLOAT32,
        address=55144,
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_b_pf = field(
        t=FieldType.FLOAT32,
        address=55146,
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_c_pf = field(
        t=FieldType.FLOAT32,
        address=55148,
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_v_avg = field(
        t=FieldType.FLOAT32,
        address=55150,
        unit="V",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )
    ac_c_avg = field(
        t=FieldType.FLOAT32,
        address=55152,
        unit="A",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    ac_c_unbalance = field(
        t=FieldType.FLOAT32,
        address=55154,
        unit="%",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_c_total = field(
        t=FieldType.FLOAT32,
        address=55156,
        unit="A",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.CURRENT,
    )
    ac_p_total = field(
        t=FieldType.FLOAT32,
        address=55158,
        unit="kW",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )
    ac_p_reactive_total = field(
        t=FieldType.FLOAT32,
        address=55160,
        unit="kVAR",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_p_apparent_total = field(
        t=FieldType.FLOAT32,
        address=55162,
        unit="kVA",
        state_class=FieldStateClass.MEASUREMENT,
    )
    ac_pf_total = field(
        t=FieldType.FLOAT32,
        address=55164,
        state_class=FieldStateClass.MEASUREMENT,
    )
    g_i_f = field(
        t=FieldType.FLOAT32,
        address=55166,
        unit="Hz",
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.FREQUENCY,
    )
    g_i_e_total = field(
        t=FieldType.FLOAT32,
        address=55168,
        unit="kWh",
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
    )
    g_o_e_total = field(
        t=FieldType.FLOAT32,
        address=55170,
        unit="kWh",
        state_class=FieldStateClass.TOTAL_INCREASING,
        device_class=DeviceClass.ENERGY,
    )
