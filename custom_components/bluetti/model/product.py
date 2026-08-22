
from pydantic import BaseModel


class UserProduct(BaseModel):
    """"""
    sn: str
    stateList: list
    online: str
    model: str | None = None
    name: str | None = None
    isBindByCurUser: str | None = None

