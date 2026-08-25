from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

@dataclass
class UserProductDecryptInfo(BaseModel):
    """"""
    sn: str
    encryptKey: Optional[str] = None
    protoType: Optional[str] = None
    protoBufFileUrl: Optional[str] = None

