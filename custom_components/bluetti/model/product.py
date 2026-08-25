from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

@dataclass
class UserProduct(BaseModel):
    """"""
    sn: str
    stateList: list
    online: str
    model: Optional[str] = None
    name: Optional[str] = None
    isBindByCurUser: Optional[str] = None
    # True:device have network model,False device have no network model
    supportNetwork: Optional[str] = None
    
    # device key
    server_key: Optional[str] = None
    server_key_reload_time: Optional[float] = 0.0
    proto_file_url: Optional[str] = None
    control_mode: Optional[str] = 'cloud'

