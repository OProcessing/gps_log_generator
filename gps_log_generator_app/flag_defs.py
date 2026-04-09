# -*- coding: utf-8 -*-
"""
DB FLAG 비트 정의. 필터 UI 및 문서화용.
"""
# FLAG 비트 정의 (2진 플래그)
FLAG_DEFINITIONS = (
    (0x0000, "dfNone", "None"),
    (0x0001, "dfBusLane", "BUSLANE - Buslane control"),
    (0x0002, "dfTrafficLights", "TRAFFICLIGHTS - Traffic lights control"),
    (0x0004, "dfBackShot", "BACKSHOT - Backshot control"),
    (0x0008, "dfZebra", "ZEBRA - Crosswalk control"),
    (0x0010, "dfObochina", "OBOCHINA - Roadside control"),
    (0x0020, "dfParkingCtrl", "PARKINGCTRL - Parking Control"),
    (0x0040, "dfStartCas", "STARTCAS - Start CAS"),
    (0x0080, "dfFinishCas", "FINISHCAS - Finish CAS"),
    (0x0100, "dfSpeedVar", "SPEEDVAR - no used"),
    (0x0200, "dfRectangle", "RECTANGLE - no used"),
    (0x0400, "dfRazmetka", "RAZMETKA - Roadlane control"),
    (0x0800, "dfUnknown", "??? - K-band radar gun"),
)


def flag_mask_from_indices(checked_indices: set[int]) -> int:
    """선택된 FLAG 인덱스(0-based)에 해당하는 비트마스크 OR. dfNone(0)은 제외."""
    mask = 0
    for i in checked_indices:
        if 0 <= i < len(FLAG_DEFINITIONS):
            mask |= FLAG_DEFINITIONS[i][0]
    return mask
