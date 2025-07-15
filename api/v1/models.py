from pydantic import BaseModel
from typing import List, Optional


class InterfaceData(BaseModel):
    max_traffic_up: int
    max_traffic_down: int
    tipo: str
    nome: str
    max_out: Optional[float] = 0.0
    avg_in: Optional[float] = 0.0
    avg_out: Optional[float] = 0.0
    client_side: Optional[bool] = False
    traffic_in: Optional[float] = 0.0
    max_in: Optional[float] = 0.0
    traffic_out: Optional[float] = 0.0
    traffic_graph_id: Optional[int] = None


class SmokeData(BaseModel):
    loss: Optional[float] = 0.0
    avg_val: Optional[float] = 0.0
    max_loss: Optional[float] = 0.0
    val: Optional[float] = 0.0
    max_val: Optional[float] = 0.0
    avg_loss: Optional[float] = 0.0


class InstitutionData(BaseModel):
    interfaces: List[InterfaceData]
    smoke: Optional[SmokeData] = None


class ViaIpeInstitution(BaseModel):
    lat: str
    lng: str
    data: InstitutionData
    id: str
    name: str
