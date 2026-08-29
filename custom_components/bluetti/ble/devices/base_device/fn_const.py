class PROTO_FN_CODE:
    DeviceSN: str = "deviceSn"
    PowerOn: str = "SetCtrlPowerOn"
    IotState: str ="iotState"
    InvWorkState: str = "InvWorkState"
    SleepState: str ="iotState:Sleep"
    WorkMode: str = "SetCtrlWorkMode"
    WorkModeBalco: str = "SetCtrlWorkModeBalco"
    RemoteSet:str = "remoteSet"
    RemoteSetSoc:str = "remoteSetSoc"
    SetAC: str = "SetCtrlAc"
    SetDC: str = "SetCtrlDc"
    SOC: str = "SOC"
    SetDCECO: str = "SetDCECO"
    SetACECO: str = "SetACECO"
    ACLoadAllTotalPower: str = "ACLoadAllTotalPower"
    DCLoadAllTotalPower: str = "DCLoadAllTotalPower"
    PVAllTotalPower: str = "PVAllTotalPower"
    GridAllTotalPower: str = "GridAllTotalPower"
    DrivingChargingPower: str = "drivingChargingPower"
    BalcoStandby: str = "SetCtrlStandby"

    # unuse
    # ACLoadTotalPower: str = "ACLoadTotalPower" #AC out cur power
    # InvACLoadTotalEnergy: str = "InvACLoadTotalEnergy" #AC out total energy
    # dailyAcLoadTotalEnegry: str = "dailyAcLoadTotalEnegry" #AC out today energy
    # DCLoadTotalPower: str = "DCLoadTotalPower" #DC out cur power
    # DCLoadTotalEnergy: str = "DCLoadTotalEnergy" #DC out total energy
    # dailyDcLoadTotalEnegry: str = "dailyDcLoadTotalEnegry" #DC out today energy
    # GridTotalChargingPower: str = "GridTotalChargingPower" #Grid in power
    # InvGridTotalChargingEnergy: str = "GridTotalChargingEnergy" #Grid charge energy
    # dailyGridTotalChargingEnergy: str = "dailyGridTotalChargingEnergy" #Grid charge today energy
    # PvTotalChargingPower: str = "PvTotalChargingPower" #PV in power 
    # InvPvTotalChargingEnergy: str = "InvPvTotalChargingEnergy" #PV charge energy
    # dailyPvTotalChargingEnergy: str = "dailyPvTotalChargingEnergy" #PV charge today energy
    # SelfConsumptionPercent: str = "SelfConsumptionPercent" #自给率 自给率(1-（电网带载的电量/负载总消耗电量）)

    ChargingStatus: str = "sChargingStatus"
    PackChgTime: str = "ChgFullTime"
    PackDsgTime: str = "DsgFullTime"
    SleepModeFnCode = "SetSleepMode"
    # for gen1 device
    DeviceSNG1: str = "sDeviceSnID"
    SetAcOutputEnableG1: str = "setAcOutputEnable"
    SetDcOutputEnableG1: str = "setDcOutputEnable"
    SystemBatterySocG1: str = "bSystemBatterySoc"
    SetSystemPowerOnG1: str = "setSystemPowerOn"
    InvWorkStatusG1: str = "aInvWorkStatus"
    SystemChgFullTimeG1: str = "bSystemChgFullTime"
    SystemDsgEmptyTimeG1: str = "bSystemDsgEmptyTime"
    SetSystemWorkModeG1: str = "setSystemWorkMode"
    SetDCECOEnableG1: str = "setDC-ECOEnable"
    SetACECOEnableG1: str = "setAC-ECOEnable"
    PowerDcDischargeG1: str = "bPowerDcDischarge"
    PowerAcDischargeG1: str = "bPowerAcDischarge"
    PowerPvChargeG1: str = "bPowerPvCharge"
    PowerGridChargeG1: str = "bPowerGridCharge"

    
class DEVICE_PROTO_VER:
    G1 = "gen1"
    G2 = "gen2"