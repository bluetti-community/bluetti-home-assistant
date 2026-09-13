"""
Home Assistant entity metadata (device_class/state_class/entity_category) for
each bluetti_modbus_lib field name.

This lives here, not in bluetti_modbus_lib, deliberately: device_class,
state_class, and entity_category are Home Assistant entity concepts, not
Modbus/protocol ones - they describe how a value should be presented in an
HA UI, which is this integration's job, not the device library's. (Feedback
from Paul Schoutsen, applied by removing the library's own
FieldCategory/FieldStateClass/DeviceClass enums - see VENDORED.md.)

Built from bluetti-registers' modbus-tcp/{balco260,ep2000}.json schemas,
which still carry this classification as data.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory


@dataclass(frozen=True)
class ModbusFieldMetadata:
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    category: EntityCategory | None = None


def suggested_precision_for_scale(scale: float) -> int | None:
    """
    Decimal places implied by a scaled field's own scale factor.

    None for an unscaled field (scale == 1.0): Home Assistant's own
    precision auto-detection already lands on 0 for those. A *scaled* field
    (0.1-scale battery voltage or grid frequency, say) needs this explicit -
    otherwise that auto-detection guesses from whichever value happens to be
    read first, which can under-round it to a whole number depending on
    what that first sample was. Ported from the same fix on the
    home-assistant/core bluetti_modbus submission.
    """
    if scale == 1.0:
        return None
    return max(0, len(f"{scale:.10f}".rstrip("0").split(".")[1]))


_POWER = ModbusFieldMetadata(device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT)
_VOLTAGE = ModbusFieldMetadata(device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT)
_CURRENT = ModbusFieldMetadata(device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT)
_ENERGY_DIAGNOSTIC = ModbusFieldMetadata(
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    category=EntityCategory.DIAGNOSTIC,
)
_DIAGNOSTIC = ModbusFieldMetadata(category=EntityCategory.DIAGNOSTIC)
_DIAGNOSTIC_MEASUREMENT = ModbusFieldMetadata(
    state_class=SensorStateClass.MEASUREMENT, category=EntityCategory.DIAGNOSTIC
)
_MEASUREMENT = ModbusFieldMetadata(state_class=SensorStateClass.MEASUREMENT)
_CONFIG = ModbusFieldMetadata(category=EntityCategory.CONFIG)

MODBUS_FIELD_METADATA: dict[str, ModbusFieldMetadata] = {
    "d_num_inverters": _DIAGNOSTIC,
    "ac_o_p_total": _POWER,
    "pv_i_p_total": _POWER,
    "g_i_p_total": _POWER,
    "d_inverter_total": _POWER,
    "pv_ac_p": _POWER,
    "ac_o_e_total": _ENERGY_DIAGNOSTIC,
    "pv_i_e_total": _ENERGY_DIAGNOSTIC,
    "g_i_e_total": _ENERGY_DIAGNOSTIC,
    "g_o_e_total": _ENERGY_DIAGNOSTIC,
    "pv_ac_e": _ENERGY_DIAGNOSTIC,
    "d_inverter_status": _DIAGNOSTIC,
    "d_inverter_warning": _DIAGNOSTIC,
    "d_inverter_fault": _DIAGNOSTIC,
    "d_inverter_type": _DIAGNOSTIC,
    "g_i_f": ModbusFieldMetadata(
        device_class=SensorDeviceClass.FREQUENCY, state_class=SensorStateClass.MEASUREMENT
    ),
    "pv_1_i_p": _POWER,
    "pv_1_i_v": _VOLTAGE,
    "pv_1_i_c": _CURRENT,
    "pv_2_i_p": _POWER,
    "pv_2_i_v": _VOLTAGE,
    "pv_2_i_c": _CURRENT,
    "pv_3_i_p": _POWER,
    "pv_3_i_v": _VOLTAGE,
    "pv_3_i_c": _CURRENT,
    "pv_4_i_p": _POWER,
    "pv_4_i_v": _VOLTAGE,
    "pv_4_i_c": _CURRENT,
    "d_num_battery_packs": _DIAGNOSTIC,
    "b_v_total": _VOLTAGE,
    "b_c_total": _CURRENT,
    # Not device_class=BATTERY - a device can only have one "the battery"
    # entity for HA's Devices-page summary column, and b_soc (the always-
    # populated reading) is that one. The identical bug (b_soc_total and
    # b_soc both BATTERY-class) was confirmed against real hardware in
    # hassio-bluetti-modbus - same fix applies here.
    "b_soc_total": _MEASUREMENT,
    "b_soh_total": _DIAGNOSTIC_MEASUREMENT,
    "b_type": _DIAGNOSTIC,
    "b_v": _VOLTAGE,
    "b_c": _CURRENT,
    "b_soc": ModbusFieldMetadata(
        device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT
    ),
    "b_soh": _DIAGNOSTIC_MEASUREMENT,
    "b_cycle_count": _DIAGNOSTIC_MEASUREMENT,
    "b_t_avg": ModbusFieldMetadata(
        device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT
    ),
    "b_cell_count": _DIAGNOSTIC,
    "b_ntc_count": _DIAGNOSTIC,
    "b_i_e": _ENERGY_DIAGNOSTIC,
    "b_o_e": _ENERGY_DIAGNOSTIC,
    "ac_o_switch": ModbusFieldMetadata(),
    "g_i_switch": ModbusFieldMetadata(),
    "g_o_switch": ModbusFieldMetadata(),
    "b_soc_low": _CONFIG,
    "b_soc_high": _CONFIG,
    # Added with bluetti-registers 0.0.30's 65 new Balco260 fields - see
    # bluetti-registers' own modbus-tcp/balco260.json for the source data
    # these classifications are transcribed from. d_serial/d_ver_arm/
    # d_ver_dsp are handled separately (excluded from sensors, fed into
    # DeviceInfo instead - see sensor.py/modbus_entity.py), matching
    # home-assistant/core's bluetti_modbus integration.
    "g_i_p_local": _POWER,
    "ac_o_p_local": _POWER,
    "pv_i_p_local": _POWER,
    "pv_ac_p_local": _POWER,
    "g_i_e_local": _ENERGY_DIAGNOSTIC,
    "g_o_e_local": _ENERGY_DIAGNOSTIC,
    "ac_o_e_local": _ENERGY_DIAGNOSTIC,
    "pv_i_e_local": _ENERGY_DIAGNOSTIC,
    "pv_ac_e_local": _ENERGY_DIAGNOSTIC,
    "d_self_consumption": _MEASUREMENT,
    "d_phase_count": _DIAGNOSTIC,
    "ac_phase_count": _DIAGNOSTIC,
    "d_inverter_phase_count": _DIAGNOSTIC,
    "g_1_i_p": _POWER,
    "g_1_i_v": _VOLTAGE,
    "g_1_i_c": _CURRENT,
    "g_2_i_p": _POWER,
    "g_2_i_v": _VOLTAGE,
    "g_2_i_c": _CURRENT,
    "g_3_i_p": _POWER,
    "g_3_i_v": _VOLTAGE,
    "g_3_i_c": _CURRENT,
    "ac_1_o_p": _POWER,
    "ac_1_o_v": _VOLTAGE,
    "ac_1_o_c": _CURRENT,
    "ac_2_o_p": _POWER,
    "ac_2_o_v": _VOLTAGE,
    "ac_2_o_c": _CURRENT,
    "ac_3_o_p": _POWER,
    "ac_3_o_v": _VOLTAGE,
    "ac_3_o_c": _CURRENT,
    "d_inverter_1_status": _DIAGNOSTIC,
    "d_inverter_1_p": _POWER,
    "d_inverter_1_v": _VOLTAGE,
    "d_inverter_1_c": _CURRENT,
    "d_inverter_2_status": _DIAGNOSTIC,
    "d_inverter_2_p": _POWER,
    "d_inverter_2_v": _VOLTAGE,
    "d_inverter_2_c": _CURRENT,
    "d_inverter_3_status": _DIAGNOSTIC,
    "d_inverter_3_p": _POWER,
    "d_inverter_3_v": _VOLTAGE,
    "d_inverter_3_c": _CURRENT,
    "pv_count": _DIAGNOSTIC,
    "pv_1_i_type": _DIAGNOSTIC,
    "pv_2_i_type": _DIAGNOSTIC,
    "pv_3_i_type": _DIAGNOSTIC,
    "pv_4_i_type": _DIAGNOSTIC,
    "b_status": _DIAGNOSTIC,
    "b_time_to_full_total": _DIAGNOSTIC,
    "b_time_to_empty_total": _DIAGNOSTIC,
    "b_serial": _DIAGNOSTIC,
    "b_ver_1": _DIAGNOSTIC,
    "b_ver_2": _DIAGNOSTIC,
    "b_ver_3": _DIAGNOSTIC,
    "b_ver_4": _DIAGNOSTIC,
    "b_protect": _DIAGNOSTIC,
    "b_error": _DIAGNOSTIC,
    "b_alarm_residential": _DIAGNOSTIC,
    "b_alarm_portable": _DIAGNOSTIC,
    "b_time_to_full": _DIAGNOSTIC,
    "b_time_to_empty": _DIAGNOSTIC,
    "d_iot_model": _DIAGNOSTIC,
    "d_iot_serial": _DIAGNOSTIC,
    "d_iot_ver": _DIAGNOSTIC,
}


def modbus_metadata_for(field_name: str) -> ModbusFieldMetadata:
    """Return the HA entity metadata for a Modbus field, or a metadata-less default."""
    return MODBUS_FIELD_METADATA.get(field_name, ModbusFieldMetadata())
