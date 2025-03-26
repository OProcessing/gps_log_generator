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


def generate(latitude=55.7558, longitude=37.6173, 
        start_speed=10, end_speed=180, step_speed=5, 
        distance_coeff=1, heading=0, iterations=50):
    
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    file_path = os.path.join(desktop_path, "gpslogtest.txt")
    speed = start_speed
    step_distance_deg = 0.00005 * distance_coeff

    with open(file_path, "w", encoding="utf-8") as f:
        for i in range(iterations):

            log_str = generate_log(latitude, longitude, speed, heading)
            f.write(log_str + "\n")

            heading_rad = math.radians(heading)
            delta_lat = step_distance_deg * math.cos(heading_rad)
            delta_lon = step_distance_deg * math.sin(heading_rad)

            latitude += delta_lat
            longitude += delta_lon

            speed += step_speed
            if speed > end_speed:
                speed = start_speed

    print("\n*************************************\n")
    print(f"Log file saved to {file_path}")
    print(f"Speed range: {start_speed}-{end_speed} km/h, step: {step_speed} km/h, Heading: {heading}° ")
    print(f"end location : {latitude:.6f}, {longitude:.6f}")
    print("\n*************************************\n")
