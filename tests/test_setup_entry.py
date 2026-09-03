"""Tests for the async_setup_entry() function of each entity platform."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory
from pybluetti import UnifyResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti import BluettiRuntimeData
from custom_components.bluetti.binary_sensor import BluettiBinarySensor
from custom_components.bluetti.binary_sensor import (
    async_setup_entry as binary_sensor_setup_entry,
)
from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.models import BluettiData, BluettiDevice
from custom_components.bluetti.number import BluettiModbusNumber
from custom_components.bluetti.number import async_setup_entry as number_setup_entry
from custom_components.bluetti.select import BluettiSelect
from custom_components.bluetti.select import async_setup_entry as select_setup_entry
from custom_components.bluetti.sensor import (
    BluettiEnergySensor,
    BluettiEstimatedBatteryPowerSensor,
    BluettiModbusSensor,
    BluettiSensor,
)
from custom_components.bluetti.sensor import (
    async_setup_entry as sensor_setup_entry,
)
from custom_components.bluetti.switch import BluettiSwitch
from custom_components.bluetti.switch import async_setup_entry as switch_setup_entry


def _entry_with_devices(hass, devices: list[BluettiDevice], modbus_coordinators=None) -> MockConfigEntry:
    for device in devices:
        device.coordinator = MagicMock()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    bluetti_data = BluettiData.__new__(BluettiData)
    bluetti_data.devices = devices
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=bluetti_data,
        stomp_client=MagicMock(),
        coordinators={},
        modbus_coordinators=modbus_coordinators or {},
    )
    return entry


async def test_sensor_setup_entry_creates_expected_entities(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
            {
                "fnCode": "InvWorkState", "fnName": "Inverter", "fnValue": "1", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.ENUM", "unit": None},
                "supportModeValues": [{"code": "1", "name": "Grid"}],
            },
            {
                "fnCode": "Weird", "fnName": "Weird sensor", "fnValue": "1", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.UNKNOWN", "unit": None},
            },
            {"fnCode": "onLine", "fnName": "Online", "fnValue": "1", "fnType": "SENSOR"},
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    # SOC + InvWorkState sensors; onLine is a binary_sensor entity, set up by
    # the binary_sensor platform instead (see test_binary_sensor_setup_entry_*).
    assert len(added) == 2
    sensors = [e for e in added if isinstance(e, BluettiSensor)]
    assert len(sensors) == 2
    assert not any(isinstance(e, BluettiBinarySensor) for e in added)

    enum_sensor = next(s for s in sensors if s._state_obj.fn_code == "InvWorkState")
    assert enum_sensor.native_value == "Grid"  # exercises the support_mode_values branch
    assert enum_sensor.options == ["Grid"]


async def test_binary_sensor_setup_entry_creates_expected_entities(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
            {"fnCode": "onLine", "fnName": "Online", "fnValue": "1", "fnType": "SENSOR"},
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await binary_sensor_setup_entry(hass, entry, added.extend)

    assert len(added) == 1
    binary_sensor = added[0]
    assert isinstance(binary_sensor, BluettiBinarySensor)
    assert binary_sensor.is_on is True
    # entity_id is derived from the platform async_add_entities was invoked
    # through, not the entity class - domain correctness is exercised by the
    # real config-entry setup test in test_init.py, this only proves the
    # entity itself is produced.


async def test_binary_sensor_setup_entry_with_no_matching_states_adds_nothing(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    entry = _entry_with_devices(hass, [device])
    async_add_entities = MagicMock()

    result = await binary_sensor_setup_entry(hass, entry, async_add_entities)

    assert result is True
    async_add_entities.assert_not_called()


async def test_sensor_setup_entry_survives_sensor_info_missing_unit_key(hass):
    # Regression test for #101/#102: real API responses can omit the "unit"
    # key entirely from sensorInfo (not just set it to None) for types like
    # ENUM. A plain state.sensor_info["unit"] KeyError there used to abort
    # the whole setup loop, silently dropping every not-yet-processed
    # sensor on every device - not just the one with the missing key.
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="EL400",
        state_list=[
            {
                "fnCode": "InvWorkState", "fnName": "Inverter", "fnValue": "1", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.ENUM"},  # no "unit" key at all
                "supportModeValues": [{"code": "1", "name": "Grid"}],
            },
            {
                "fnCode": "GridAllTotalPower", "fnName": "Grid Input Power", "fnValue": "100", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    sensors = [e for e in added if isinstance(e, BluettiSensor)]
    assert {s._state_obj.fn_code for s in sensors} == {"InvWorkState", "GridAllTotalPower"}


async def test_sensor_setup_entry_creates_energy_sensor_for_power_sensors(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260",
        state_list=[
            {
                "fnCode": "PVAllTotalPower", "fnName": "PV Input Power", "fnValue": "100", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    # Power sensor + its energy companion + the plain (non-power) battery sensor.
    assert len(added) == 3
    energy_sensors = [e for e in added if isinstance(e, BluettiEnergySensor)]
    assert len(energy_sensors) == 1
    assert energy_sensors[0].unique_id == "SN1_PVAllTotalPower_energy"
    assert energy_sensors[0].native_unit_of_measurement == "kWh"


async def test_sensor_setup_entry_creates_estimated_battery_power_sensors(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260",
        state_list=[
            {
                "fnCode": "PVAllTotalPower", "fnName": "PV Input Power", "fnValue": "500", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "GridAllTotalPower", "fnName": "Grid Input Power", "fnValue": "0", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "ACLoadAllTotalPower", "fnName": "AC Load Power", "fnValue": "200", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    estimated = [e for e in added if isinstance(e, BluettiEstimatedBatteryPowerSensor)]
    assert len(estimated) == 2
    charge = next(e for e in estimated if e.unique_id == "SN1_EstimatedBatteryChargePower")
    discharge = next(e for e in estimated if e.unique_id == "SN1_EstimatedBatteryDischargePower")
    # 500 W PV - 200 W AC load = 300 W surplus available to charge.
    assert charge.native_value == 300.0
    assert discharge.native_value == 0.0

    energy_companion_ids = {
        "SN1_EstimatedBatteryChargePower_energy",
        "SN1_EstimatedBatteryDischargePower_energy",
    }
    energy_companions = [
        e for e in added if isinstance(e, BluettiEnergySensor) and e.unique_id in energy_companion_ids
    ]
    assert len(energy_companions) == 2


async def test_sensor_setup_entry_creates_estimated_battery_power_sensors_for_ep2000(hass):
    # EBOX-EP2000 reports the same three power states as Balco260, and no
    # diagnostics dump for either model has ever shown a DC-load fn_code -
    # the same evidence that validates Balco260 covers EP2000 too.
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="EBOX-EP2000",
        state_list=[
            {
                "fnCode": "PVAllTotalPower", "fnName": "PV Input Power", "fnValue": "500", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "GridAllTotalPower", "fnName": "Grid Input Power", "fnValue": "0", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "ACLoadAllTotalPower", "fnName": "AC Load Power", "fnValue": "200", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    assert any(isinstance(e, BluettiEstimatedBatteryPowerSensor) for e in added)


async def test_sensor_setup_entry_skips_estimated_battery_sensors_for_unvalidated_model(hass):
    # Regression test: the estimate used to activate for any model exposing
    # PV/grid/AC-load totals, even though it deliberately omits DC load and
    # is only validated for Balco260 - a model with real DC output could
    # otherwise get a materially wrong charge/discharge reading.
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[
            {
                "fnCode": "PVAllTotalPower", "fnName": "PV Input Power", "fnValue": "500", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "GridAllTotalPower", "fnName": "Grid Input Power", "fnValue": "0", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "ACLoadAllTotalPower", "fnName": "AC Load Power", "fnValue": "200", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    assert not any(isinstance(e, BluettiEstimatedBatteryPowerSensor) for e in added)


async def test_sensor_setup_entry_skips_estimated_battery_sensors_when_data_missing(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    assert not any(isinstance(e, BluettiEstimatedBatteryPowerSensor) for e in added)


async def test_sensor_setup_entry_with_no_matching_states_adds_nothing(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    entry = _entry_with_devices(hass, [device])
    async_add_entities = MagicMock()

    result = await sensor_setup_entry(hass, entry, async_add_entities)

    assert result is True
    async_add_entities.assert_not_called()


async def test_switch_setup_entry_creates_switch_and_controls_it(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    device._api_client = MagicMock()
    entry = _entry_with_devices(hass, [device])
    added = []

    await switch_setup_entry(hass, entry, added.extend)

    assert len(added) == 1
    switch = added[0]
    assert isinstance(switch, BluettiSwitch)
    assert switch.is_on is False

    async def fake_control_device(payload):
        return UnifyResponse(msgId="1", msgCode=0)

    device._api_client.control_device = fake_control_device
    await switch.async_turn_on()
    assert switch.is_on is True

    await switch.async_turn_off()
    assert switch.is_on is False


async def test_select_setup_entry_creates_select_and_controls_it(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{
            "fnCode": "SetCtrlWorkMode", "fnName": "Mode", "fnValue": "0", "fnType": "SELECT",
            "supportModeValues": [{"code": "0", "name": "Standard"}, {"code": "1", "name": "Silent"}],
        }],
    )
    device._api_client = MagicMock()
    entry = _entry_with_devices(hass, [device])
    added = []

    await select_setup_entry(hass, entry, added.extend)

    assert len(added) == 1
    select = added[0]
    assert isinstance(select, BluettiSelect)

    async def fake_control_device(payload):
        return UnifyResponse(msgId="1", msgCode=0)

    device._api_client.control_device = fake_control_device
    await select.async_select_option("Silent")
    assert select.current_option == "Silent"


async def test_sensor_setup_entry_creates_modbus_sensors_grouped_with_cloud_device(hass):
    from enum import Enum
    from types import SimpleNamespace

    from bluetti_modbus_lib.modbus.client import ClientReturnValue

    class _FakeInverterStatus(Enum):
        STANDBY = 0

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260",
        state_list=[
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
        ],
    )
    # device_class/state_class/entity_category are no longer carried on
    # ClientReturnValue (bluetti_modbus_lib doesn't know about HA entity
    # concepts) - BluettiModbusSensor looks them up in
    # modbus_field_metadata.MODBUS_FIELD_METADATA by field name instead, so
    # these real field names exercise that lookup, not a mocked value.
    fields = {
        # Excluded - duplicates the cloud SOC sensor already added above.
        "b_soc": ClientReturnValue(name="b_soc", unit="%", value=42),
        "b_cycle_count": ClientReturnValue(name="b_cycle_count", unit=None, value=12),
        # CONFIG must be remapped to DIAGNOSTIC - SensorEntity forbids CONFIG.
        "b_soc_high": ClientReturnValue(name="b_soc_high", unit="%", value=100),
        "d_inverter_status": ClientReturnValue(
            name="d_inverter_status", unit=None, value=_FakeInverterStatus.STANDBY
        ),
        "g_i_f": ClientReturnValue(name="g_i_f", unit="Hz", value=50.0),
        # Excluded - the device's own identity, fed into DeviceInfo instead.
        "d_serial": ClientReturnValue(name="d_serial", unit=None, value=123456),
    }
    # Real scale for g_i_f (0.1) drives suggested_display_precision; every
    # other field here defaults to an unscaled register. b_soc_high is not
    # writable on this (mocked) device - number.py's own tests cover the
    # writable case, where it's excluded here instead.
    scales = {"g_i_f": 0.1}
    modbus_coordinator = MagicMock(data=fields)
    modbus_coordinator.device.get_field.side_effect = (
        lambda name: SimpleNamespace(scale=scales.get(name, 1.0), writable=False)
    )

    entry = _entry_with_devices(hass, [device], modbus_coordinators={"SN1": modbus_coordinator})
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    modbus_sensors = {s._field_name: s for s in added if isinstance(s, BluettiModbusSensor)}
    assert set(modbus_sensors) == {"b_cycle_count", "b_soc_high", "d_inverter_status", "g_i_f"}

    cloud_sensor = next(e for e in added if isinstance(e, BluettiSensor))
    assert modbus_sensors["b_cycle_count"].device_info["identifiers"] == cloud_sensor.device_info["identifiers"]

    assert modbus_sensors["g_i_f"].device_class == SensorDeviceClass.FREQUENCY
    assert modbus_sensors["g_i_f"].state_class == SensorStateClass.MEASUREMENT
    assert modbus_sensors["g_i_f"].suggested_display_precision == 1
    assert modbus_sensors["b_cycle_count"].suggested_display_precision is None

    assert modbus_sensors["b_soc_high"].entity_category == EntityCategory.DIAGNOSTIC
    assert modbus_sensors["b_cycle_count"].native_value == 12
    assert modbus_sensors["d_inverter_status"].native_value == "STANDBY"

    modbus_coordinator.data = {}
    assert modbus_sensors["b_cycle_count"].native_value is None


async def test_sensor_setup_entry_excludes_writable_soc_thresholds(hass):
    # Where bluetti_modbus_lib marks b_soc_low/b_soc_high writable=True
    # (Balco260), number.py creates the entity instead - sensor.py must not
    # also add a duplicate read-only one for the same register.
    from types import SimpleNamespace

    from bluetti_modbus_lib.modbus.client import ClientReturnValue

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260", state_list=[],
    )
    fields = {"b_soc_low": ClientReturnValue(name="b_soc_low", unit="%", value=10)}
    modbus_coordinator = MagicMock(data=fields)
    modbus_coordinator.device.get_field.return_value = SimpleNamespace(scale=1.0, writable=True)

    entry = _entry_with_devices(hass, [device], modbus_coordinators={"SN1": modbus_coordinator})
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    assert added == []


async def test_sensor_setup_entry_skips_modbus_coordinator_for_unknown_device(hass):
    entry = _entry_with_devices(hass, [], modbus_coordinators={"UNKNOWN_SN": MagicMock(data={})})
    added = []

    result = await sensor_setup_entry(hass, entry, added.extend)

    assert result is True
    assert added == []


async def test_number_setup_entry_creates_an_entity_per_writable_field(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260", state_list=[],
    )
    modbus_coordinator = MagicMock(data={})
    modbus_coordinator.device.get_field.return_value = MagicMock(writable=True)

    entry = _entry_with_devices(hass, [device], modbus_coordinators={"SN1": modbus_coordinator})
    added = []

    result = await number_setup_entry(hass, entry, added.extend)

    assert result is True
    numbers = {e._field_name: e for e in added if isinstance(e, BluettiModbusNumber)}
    assert set(numbers) == {"b_soc_low", "b_soc_high"}
    assert numbers["b_soc_low"].native_min_value == 0
    assert numbers["b_soc_low"].native_max_value == 100


async def test_number_setup_entry_skips_a_field_that_is_not_writable(hass):
    # e.g. EP2000 today: the schema knows about b_soc_low/b_soc_high, but
    # bluetti_modbus_lib doesn't mark them writable there yet.
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="EP2000", state_list=[],
    )
    modbus_coordinator = MagicMock(data={})
    modbus_coordinator.device.get_field.return_value = MagicMock(writable=False)

    entry = _entry_with_devices(hass, [device], modbus_coordinators={"SN1": modbus_coordinator})
    added = []

    await number_setup_entry(hass, entry, added.extend)

    assert added == []


async def test_number_setup_entry_skips_a_field_the_device_does_not_have(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="SMeter", state_list=[],
    )
    modbus_coordinator = MagicMock(data={})
    modbus_coordinator.device.get_field.return_value = None

    entry = _entry_with_devices(hass, [device], modbus_coordinators={"SN1": modbus_coordinator})
    added = []

    await number_setup_entry(hass, entry, added.extend)

    assert added == []


async def test_number_setup_entry_skips_modbus_coordinator_for_unknown_device(hass):
    entry = _entry_with_devices(hass, [], modbus_coordinators={"UNKNOWN_SN": MagicMock(data={})})
    added = []

    result = await number_setup_entry(hass, entry, added.extend)

    assert result is True
    assert added == []


async def test_modbus_number_writes_and_reads_the_field(hass):
    from bluetti_modbus_lib.modbus.client import ClientReturnValue

    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260")
    modbus_coordinator = MagicMock(data={})
    modbus_coordinator.device.write = AsyncMock()
    number = BluettiModbusNumber(device, modbus_coordinator, "b_soc_low")

    # No value read yet.
    assert number.native_value is None

    modbus_coordinator.data = {"b_soc_low": ClientReturnValue(name="b_soc_low", unit="%", value=20)}
    assert number.native_value == 20

    await number.async_set_native_value(42.0)

    modbus_coordinator.device.write.assert_awaited_once_with("b_soc_low", 42)
    # Not optimistic - native_value still reads live from coordinator.data,
    # unchanged until the next poll actually updates it.
    assert number.native_value == 20


async def test_select_setup_entry_ignores_states_without_modes(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    entry = _entry_with_devices(hass, [device])
    async_add_entities = MagicMock()

    await select_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_not_called()
