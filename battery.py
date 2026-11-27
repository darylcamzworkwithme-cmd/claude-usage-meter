"""Read the keyboard's battery level over Bluetooth LE (standard Battery Service 0x180F / 0x2A19).

Read-only. Finds the paired keyboard by name (config.KEYBOARD_NAME); returns None if it isn't
connected over Bluetooth.
"""
import asyncio

from config import KEYBOARD_NAME

BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"


async def _read():
    from winrt.windows.devices.bluetooth import BluetoothCacheMode, BluetoothLEDevice
    from winrt.windows.devices.enumeration import DeviceInformation
    from winrt.windows.storage.streams import DataReader

    selector = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
    for info in await DeviceInformation.find_all_async_aqs_filter(selector):
        if KEYBOARD_NAME.lower() not in (info.name or "").lower():
            continue
        dev = await BluetoothLEDevice.from_id_async(info.id)
        if dev is None or dev.connection_status != 1:
            continue
        svcs = await dev.get_gatt_services_async(BluetoothCacheMode.UNCACHED)
        for svc in svcs.services:
            if str(svc.uuid).lower() != BATTERY_SERVICE:
                continue
            chars = await svc.get_characteristics_async(BluetoothCacheMode.UNCACHED)
            for ch in chars.characteristics:
                if str(ch.uuid).lower() == BATTERY_LEVEL:
                    r = await ch.read_value_async(BluetoothCacheMode.UNCACHED)
                    if r.value and r.value.length:
                        buf = bytearray(r.value.length)
                        DataReader.from_buffer(r.value).read_bytes(buf)
                        return buf[0]
    return None


def battery_percent():
    try:
        return asyncio.run(asyncio.wait_for(_read(), 10))
    except Exception:
        return None


if __name__ == "__main__":
    print("keyboard battery:", battery_percent())
