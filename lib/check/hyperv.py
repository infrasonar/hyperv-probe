import logging
from aiowmi.query import Query
from libprobe.asset import Asset
from libprobe.check import Check
from ..utils import get_state
from ..wmiquery import wmiconn, wmiquery, wmiclose

TYPE_NAME = "guests"
QUERY = Query("""
    SELECT
    ElementName, Name, Status
    FROM Msvm_ComputerSystem
    WHERE Caption = 'Virtual Machine'
""", namespace=r'root\virtualization\v2')


class CheckHyperV(Check):
    key = 'hyperv'

    @staticmethod
    async def run(asset: Asset, local_config: dict, config: dict) -> dict:
        conn, service = await wmiconn(asset, local_config, config)
        try:
            rows = await wmiquery(conn, service, QUERY)
            state = get_state(TYPE_NAME, rows)
        finally:
            wmiclose(conn, service)

        return state
