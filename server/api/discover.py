from server.api.device import Device, pydantic_batch_Device
from server.utils.configure import API, get_metadata
from server.utils.detect import KeonnFinder

kf = KeonnFinder()


async def discover_devices() -> list[pydantic_batch_Device]:  # type: ignore
    await kf.run_detection()
    found = kf.get_devices()

    found_macs = set(found.keys())
    # get only macs from the database
    db_macs = await Device.filter(mac__in=found_macs).values_list("mac", flat=True)

    new_macs = found_macs - set(db_macs)

    if not new_macs:
        return []

    to_create = []
    for mac in new_macs:
        ip = found[mac]["ip"]
        device = API(ip)
        meta = await get_metadata(device)
        to_create.append(
            Device(
                mac=mac,
                ip=ip,
                meta=meta.model_dump(),
                online=True,
                name=meta.id,
            )
        )

    await Device.bulk_create(to_create)
    return await pydantic_batch_Device.from_queryset(
        Device.filter(mac__in=new_macs).all()
    )
