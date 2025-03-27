import math
import os
from datetime import datetime

def calculate_nmea_checksum(nmea_str: str) -> str:
    cs_val = 0
    for ch in nmea_str:
        cs_val ^= ord(ch)
    return f"{cs_val:02X}"

def decimal_degrees_to_nmea(coord: float, is_lat: bool=True):
    if is_lat:
        direction = 'N' if coord >= 0 else 'S'
    else:
        direction = 'E' if coord >= 0 else 'W'
    
    abs_coord = abs(coord)
    degrees = int(abs_coord)
    minutes = (abs_coord - degrees) * 60.0
    
    minute_int = int(minutes)
    minute_frac = minutes - minute_int
    
    minute_str = f"{minute_int:02d}" + f"{minute_frac:.5f}"[1:]

    if is_lat:
        ddmm = f"{degrees:02d}" + minute_str
    else:
        ddmm = f"{degrees:03d}" + minute_str

    return ddmm, direction

def kmh_to_knots(kmh: float) -> float:
    return kmh / 1.852

def generate_gnrmc_sentence(
    utc_time: str,     
    date_str: str,     
    lat: float,        
    lon: float,        
    speed_knots: float,
    heading: float = 0.0,
    status: str = 'A', 
    mode: str = 'A'    
) -> str:
    lat_nmea, ns = decimal_degrees_to_nmea(lat, True)
    lon_nmea, ew = decimal_degrees_to_nmea(lon, False)
    speed_str = f"{speed_knots:.2f}"
    heading_str = f"{heading:.2f}"

    body = (
        f"GPRMC,{utc_time},{status},{lat_nmea},{ns},"
        f"{lon_nmea},{ew},{speed_str},{heading_str},{date_str},,,{mode}"
    )
    chksum = calculate_nmea_checksum(body)
    return f"${body}*{chksum}"

def generate_gpgga_sentence(
    utc_time: str,  
    lat: float,
    lon: float,
    fix_quality: int = 1,
    num_sat: int = 8,
    hdop: float = 1.0,
    altitude: float = 100.0,
    geoid_height: float = 30.0
) -> str:
    lat_nmea, ns = decimal_degrees_to_nmea(lat, True)
    lon_nmea, ew = decimal_degrees_to_nmea(lon, False)

    num_sat_str = f"{num_sat:02d}"
    hdop_str = f"{hdop:.1f}"
    alt_str = f"{altitude:.1f}"
    geoid_str = f"{geoid_height:.1f}"

    body = (
        f"GPGGA,{utc_time},{lat_nmea},{ns},{lon_nmea},{ew},"
        f"{fix_quality},{num_sat_str},{hdop_str},{alt_str},M,"
        f"{geoid_str},M,,"
    )
    chksum = calculate_nmea_checksum(body)
    return f"${body}*{chksum}"

def generate_gpgll_sentence(
    utc_time: str,
    lat: float,
    lon: float,
    status: str = 'A',
    mode: str = 'A'
) -> str:
    lat_nmea, ns = decimal_degrees_to_nmea(lat, True)
    lon_nmea, ew = decimal_degrees_to_nmea(lon, False)

    body = (
        f"GPGLL,{lat_nmea},{ns},{lon_nmea},{ew},"
        f"{utc_time},{status},{mode}"
    )
    chksum = calculate_nmea_checksum(body)
    return f"${body}*{chksum}"

def generate_gngsa_sentence(
    mode1: str = 'A',  
    mode2: int = 3,    
    pdop: float = 1.9,
    hdop: float = 1.1,
    vdop: float = 1.5,
    used_sats=None
) -> str:
    if used_sats is None:
        used_sats = [29, 31, 27, 32, 21, 57, 25, 14]

    used_sats = used_sats[:12]
    sat_fields = [str(prn) for prn in used_sats]
    while len(sat_fields) < 12:
        sat_fields.append('')

    sat_part = ",".join(sat_fields)
    body = (
        f"GNGSA,{mode1},{mode2},{sat_part},"
        f"{pdop:.1f},{hdop:.1f},{vdop:.1f}"
    )
    chksum = calculate_nmea_checksum(body)
    return f"${body}*{chksum}"

def generate_gpgsv_sentence(
    total_msgs: int = 3,
    msg_num: int = 1,
    sats_in_view: int = 12,
    sat_info=None
) -> str:
    if sat_info is None:
        sat_info = [
            (29, 36, 51, 38),
            (31, 70, 28, 41),
            (27, 9, 202, 34),
            (32, 12, 244, 28)
        ]
    
    sat_strs = []
    for (prn, elev, az, snr) in sat_info:
        sat_strs.append(f"{prn},{elev},{az},{snr}")
    
    while len(sat_strs) < 4:
        sat_strs.append(",,,")
    sat_data = ",".join(sat_strs)

    body = f"GPGSV,{total_msgs},{msg_num},{sats_in_view},{sat_data}"
    chksum = calculate_nmea_checksum(body)
    return f"${body}*{chksum}"

def generate_glgsv_sentence(
    total_msgs: int = 2,
    msg_num: int = 1,
    sats_in_view: int = 8,
    sat_info=None
) -> str:
    if sat_info is None:
        sat_info = [
            (84, 43, 59, 26),
            (74, 39, 59, 30),
            (85, 47, 137, 41),
            (75, 46, 340, 0),
        ]

    sat_strs = []
    for (prn, elev, az, snr) in sat_info:
        sat_strs.append(f"{prn},{elev},{az},{snr}")
    while len(sat_strs) < 4:
        sat_strs.append(",,,")
    sat_data = ",".join(sat_strs)

    body = f"GLGSV,{total_msgs},{msg_num},{sats_in_view},{sat_data}"
    chksum = calculate_nmea_checksum(body)
    return f"${body}*{chksum}"

def generate_log(latitude, longitude, speed, heading) :
    now = datetime.utcnow()
    utc_time = now.strftime('%H%M%S.') + f"{int(now.microsecond/1000):03d}"
    date_str = now.strftime('%d%m%y')
    speed_knots = kmh_to_knots(float(speed))
    rmc = generate_gnrmc_sentence(utc_time=utc_time, date_str=date_str, lat=latitude, lon=longitude, speed_knots=speed_knots, heading=heading)
    gga = generate_gpgga_sentence(utc_time=utc_time, lat=latitude, lon=longitude, fix_quality=1, num_sat=8, hdop=1.0, altitude=120.0, geoid_height=35.0)
    gll = generate_gpgll_sentence(utc_time=utc_time, lat=latitude, lon=longitude)
    gsa = generate_gngsa_sentence()
    gsv_gps = generate_gpgsv_sentence()
    gsv_glo = generate_glgsv_sentence()
    log = "\n".join([rmc, gga, gll, gsa, gsv_gps, gsv_glo])
    return log

def generate(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    start_speed: float = 10,
    end_speed: float = 180,
    step_speed: float = 5,
    distance_coeff: float = 1,
    heading: float = 0,
    iterations: int = 50
):
    if start_lat is None:
        start_lat = 55.751244
    if start_lon is None:
        start_lon = 37.618423
    if end_lat is None:
        end_lat = 55.751244
    if end_lon is None:
        end_lon = 37.618423
        
    # "lat_lon_startspeed_endspeed.txt"
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    file_name = f"{start_lat:.4f}_{start_lon:.4f}_{start_speed}_{end_speed}.txt"
    file_path = os.path.join(desktop_path, file_name)

    base_lat_diff = end_lat - start_lat
    base_lon_diff = end_lon - start_lon

    lat_step = (base_lat_diff / 100.0) * distance_coeff
    lon_step = (base_lon_diff / 100.0) * distance_coeff

    lat = start_lat
    lon = start_lon
    speed = start_speed

    with open(file_path, "w", encoding="utf-8") as f:
        for i in range(iterations):
            log_str = generate_log(lat, lon, speed, heading)
            f.write(log_str + "\n")

            lat += lat_step
            lon += lon_step

            speed += step_speed
            if speed > end_speed:
                speed = start_speed

    print("\n*************************************\n")
    print(f"Log file saved to {file_path}")
    print(f"Start location : {start_lat:.6f}, {start_lon:.6f}")
    print(f"Speed range    : {start_speed}-{end_speed} km/h (step: {step_speed})")
    print(f"Final lat,lon  : {lat:.6f}, {lon:.6f}")
    print("*************************************\n")
