# -*- coding: utf-8 -*-
"""
기준점과 방향·거리로 시작/종료 좌표 계산.
주행 로그가 기준점을 지나가도록 start는 기준점 이전, end는 기준점 이후.
"""
import math

# 위도 1도 ≈ 111.32 km, 경도 1도 ≈ 111.32 * cos(lat_rad) km
KM_PER_DEG_LAT = 111.32


def _km_per_deg_lon(lat_deg: float) -> float:
    return KM_PER_DEG_LAT * max(0.0001, math.cos(math.radians(lat_deg)))


def point_at_distance(
    lat_deg: float, lon_deg: float, heading_deg: float, distance_km: float
) -> tuple[float, float]:
    """
    (lat_deg, lon_deg)에서 heading_deg 방향(0=북, 90=동)으로 distance_km만큼 이동한 점 반환.
    """
    rad = math.radians(heading_deg)
    dlat = (distance_km / KM_PER_DEG_LAT) * math.cos(rad)
    dlon = (distance_km / _km_per_deg_lon(lat_deg)) * math.sin(rad)
    return (lat_deg + dlat, lon_deg + dlon)


def start_end_from_reference(
    ref_lat: float,
    ref_lon: float,
    direction_deg: float,
    start_dist_km: float,
    end_dist_km: float,
) -> tuple[float, float, float, float]:
    """
    기준점(ref)을 지나는 구간의 시작·종료 좌표 계산.
    - start: 기준점에서 방향의 반대로 start_dist_km 만큼 떨어진 점
    - end: 기준점에서 방향으로 end_dist_km 만큼 떨어진 점
    반환: (start_lat, start_lon, end_lat, end_lon)
    """
    reverse = (direction_deg + 180) % 360
    start_lat, start_lon = point_at_distance(ref_lat, ref_lon, reverse, start_dist_km)
    end_lat, end_lon = point_at_distance(ref_lat, ref_lon, direction_deg, end_dist_km)
    return start_lat, start_lon, end_lat, end_lon
