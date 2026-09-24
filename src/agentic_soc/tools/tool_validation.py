from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints


class StrictToolInput(BaseModel):

   model_config = ConfigDict(extra="forbid")


AWSActionName = Annotated[
   str,
   StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9]*$")
]