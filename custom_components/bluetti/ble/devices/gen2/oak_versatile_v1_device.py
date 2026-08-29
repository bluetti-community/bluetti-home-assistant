from typing import Any, List
import logging

from ....models import BluettiDevice
from ..base_device.oak_device_gen2 import OakDeviceGen2
from ...utils.commands import OakReadCmd,OakWriteCmd
from ..base_device.fn_const import PROTO_FN_CODE

__LOGGER__ = logging.getLogger(__name__)

class OakVersatileV1Device(OakDeviceGen2):
    SUPPORTED_MODELS = {"EL400","EL320,AORA320","PR200V2,Elite 200 V2,AORA200,AORA200V2"}
    SUPPORTED_MODELS_CACHE = None

    def __init__(self, address: str,bluetti_device:BluettiDevice):
        super().__init__(address,bluetti_device)

    # this is app300 el400 (...) sleep mode op logic
    def build_sleep_cmd(self,fn_value) -> list[OakWriteCmd]:
        remote_cmds = []
        
        # verstaile sleep mode 3 or 4
        write_value = 2
        if fn_value == '1':
            remote_cmds = self.build_sleep_pre_cmd()

        sleep_cmd = OakWriteCmd(fn_code=PROTO_FN_CODE.PowerOn,write_value=write_value)
        return remote_cmds+[sleep_cmd]