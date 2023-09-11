import logging
from libprobe.asset import Asset
from libprobe.exceptions import CheckException, NoCountException


async def check_hyperv(
        asset: Asset,
        asset_config: dict,
        config: dict) -> dict:
    ...
