from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, field

# GENERATED FILE! DO NOT EDIT!


class SMeter(BluettiDevice):
    d_status = field(
        t=FieldType.UINT16,
        address=55111,
    )
    d_timestamp = field(
        t=FieldType.UINT32,
        address=55112,
    )
    ac_a_v = field(
        t=FieldType.FLOAT32,
        address=55114,
        unit="V",
    )
    ac_b_v = field(
        t=FieldType.FLOAT32,
        address=55116,
        unit="V",
    )
    ac_c_v = field(
        t=FieldType.FLOAT32,
        address=55118,
        unit="V",
    )
    ac_a_c = field(
        t=FieldType.FLOAT32,
        address=55120,
        unit="A",
    )
    ac_b_c = field(
        t=FieldType.FLOAT32,
        address=55122,
        unit="A",
    )
    ac_c_c = field(
        t=FieldType.FLOAT32,
        address=55124,
        unit="A",
    )
    ac_a_p = field(
        t=FieldType.FLOAT32,
        address=55126,
        unit="kW",
    )
    ac_b_p = field(
        t=FieldType.FLOAT32,
        address=55128,
        unit="kW",
    )
    ac_c_p = field(
        t=FieldType.FLOAT32,
        address=55130,
        unit="kW",
    )
    ac_a_p_reactive = field(
        t=FieldType.FLOAT32,
        address=55132,
        unit="kVAR",
    )
    ac_b_p_reactive = field(
        t=FieldType.FLOAT32,
        address=55134,
        unit="kVAR",
    )
    ac_c_p_reactive = field(
        t=FieldType.FLOAT32,
        address=55136,
        unit="kVAR",
    )
    ac_a_p_apparent = field(
        t=FieldType.FLOAT32,
        address=55138,
        unit="kVA",
    )
    ac_b_p_apparent = field(
        t=FieldType.FLOAT32,
        address=55140,
        unit="kVA",
    )
    ac_c_p_apparent = field(
        t=FieldType.FLOAT32,
        address=55142,
        unit="kVA",
    )
    ac_a_pf = field(
        t=FieldType.FLOAT32,
        address=55144,
    )
    ac_b_pf = field(
        t=FieldType.FLOAT32,
        address=55146,
    )
    ac_c_pf = field(
        t=FieldType.FLOAT32,
        address=55148,
    )
    ac_v_avg = field(
        t=FieldType.FLOAT32,
        address=55150,
        unit="V",
    )
    ac_c_avg = field(
        t=FieldType.FLOAT32,
        address=55152,
        unit="A",
    )
    ac_c_unbalance = field(
        t=FieldType.FLOAT32,
        address=55154,
        unit="%",
    )
    ac_c_total = field(
        t=FieldType.FLOAT32,
        address=55156,
        unit="A",
    )
    ac_p_total = field(
        t=FieldType.FLOAT32,
        address=55158,
        unit="kW",
    )
    ac_p_reactive_total = field(
        t=FieldType.FLOAT32,
        address=55160,
        unit="kVAR",
    )
    ac_p_apparent_total = field(
        t=FieldType.FLOAT32,
        address=55162,
        unit="kVA",
    )
    ac_pf_total = field(
        t=FieldType.FLOAT32,
        address=55164,
    )
    g_i_f = field(
        t=FieldType.FLOAT32,
        address=55166,
        unit="Hz",
    )
    g_i_e_total = field(
        t=FieldType.FLOAT32,
        address=55168,
        unit="kWh",
    )
    g_o_e_total = field(
        t=FieldType.FLOAT32,
        address=55170,
        unit="kWh",
    )
