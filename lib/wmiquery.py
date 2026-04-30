import asyncio
import ipaddress
import socket
import datetime
import logging
from libprobe.asset import Asset
from libprobe.exceptions import (
    CheckException,
    IgnoreCheckException,
    IgnoreResultException)
from aiowmi.query import Query
from aiowmi.connection import Connection
from aiowmi.connection import Protocol as Service
from aiowmi.exceptions import WbemExInvalidClass, WbemExInvalidNamespace
from aiowmi.kerberos.cache import KerberosCache
from .kdc import get_kdc


DTYPS_NOT_NULL = {
    int: 0,
    bool: False,
    float: 0.,
    list: [],
}
QUERY_TIMEOUT = 120
KCACHE: dict[tuple[str, str, str], KerberosCache] = {}
AUTH_NTLM = 'NTLM'
AUTH_KERBEROS = 'Kerberos'


async def wmiconn(
        asset: Asset,
        local_config: dict,
        config: dict) -> tuple[Connection, Service]:
    address = config.get('address')
    if not address:
        address = asset.name
    username = local_config.get('username')
    password = local_config.get('password')
    auth = config.get('authentication', AUTH_NTLM)
    if username is None or password is None:
        logging.error(f'missing credentials for {asset}')
        raise IgnoreResultException

    if '\\' in username:
        # Replace double back-slash with single if required
        username = username.replace('\\\\', '\\')
        domain, username = username.split('\\')
    elif '@' in username:
        username, domain = username.split('@')
    else:
        domain = ''

    # doesn't matter if we use NTLM or Kerberos
    key = address, username, password
    kcache = KCACHE.get(key)

    if auth == AUTH_KERBEROS:
        if kcache is None:
            # create TGS/TGT cache for this asset
            kcache = KCACHE[key] = KerberosCache()

        if not domain:
            raise CheckException(
                'Domain is required for Kerberos authentication. '
                f'Please format the username as {username}@DOMAIN '
                'in the probe configuration')

        if "." not in domain:
            raise CheckException(
                f"`{domain}` looks like a NetBIOS name. "
                "Kerberos requires a Full Domain Name "
                "(for example user@MY.DOMAIN.LOCAL)")

        try:
            ipaddress.ip_address(address)
            loop = asyncio.get_running_loop()
            result = await loop.getnameinfo((address, 0), socket.NI_NAMEREQD)
            address = result[0]
        except ValueError:
            pass
        except Exception as e:
            raise CheckException(
                f'Failed to read FQDN for: `{address}` '
                '(Kerberos authentication require an FQDN)')

    conn = Connection(host=address,
                      username=username,
                      password=password,
                      domain=domain,
                      kerberos_cache=kcache)
    service = None

    try:
        await conn.connect()
    except Exception as e:
        error_msg = str(e) or type(e).__name__
        raise CheckException(f'unable to connect: {error_msg}')

    try:
        if auth == AUTH_NTLM:
            service = await conn.negotiate_ntlm()
        elif auth == AUTH_KERBEROS:
            kdc_host, kdc_port = await get_kdc(domain=domain)
            conn.set_kdc(kdc_host, kdc_port)
            service = await conn.negotiate_kerberos()
        else:
            raise Exception(f'invalid auth type: {auth}')
    except Exception as e:
        conn.close()
        error_msg = str(e) or type(e).__name__
        raise Exception(f'unable to authenticate: {error_msg}')

    return conn, service


async def wmiquery(
        conn: Connection,
        service: Service,
        query: Query,
        refs: dict | None = None,
        timeout: int = QUERY_TIMEOUT) -> list[dict]:
    rows = []

    try:
        async with query.context(conn, service, timeout=timeout) as qc:
            async for props in qc.results():  # type: ignore
                row = {}
                for name, prop in props.items():
                    if refs and name in refs and prop.is_reference():
                        await refs[name](conn, service, prop, row)
                    elif prop.value is None:
                        row[name] = DTYPS_NOT_NULL.get(prop.get_type())
                    elif isinstance(prop.value, datetime.datetime):
                        row[name] = prop.value.timestamp()
                    elif isinstance(prop.value, datetime.timedelta):
                        row[name] = prop.value.seconds
                    else:
                        row[name] = prop.value
                rows.append(row)
    except (WbemExInvalidClass, WbemExInvalidNamespace):
        raise IgnoreCheckException
    except asyncio.TimeoutError:
        raise CheckException('WMI query timed out')
    except Exception as e:
        error_msg = str(e) or type(e).__name__
        # At this point log the exception as this can be useful for debugging
        # issues with WMI queries;
        logging.exception(f'query error: {error_msg};')
        raise CheckException(error_msg)
    return rows


def wmiclose(conn: Connection, service: Service):
    service.close()
    conn.close()
