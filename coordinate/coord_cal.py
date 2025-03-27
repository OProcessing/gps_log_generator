def nmea_to_decimal(nmea_coord: str, hemisphere: str, is_lat: bool = True) -> float:
    if is_lat:
        degree_digits = 2
    else:
        degree_digits = 3
    degrees = int(nmea_coord[:degree_digits])
    minutes = float(nmea_coord[degree_digits:])
    decimal_deg = degrees + minutes / 60.0
    if hemisphere.upper() in ['S', 'W']:
        decimal_deg = -decimal_deg

    return decimal_deg


def nmea_sentence_to_decimal(nmea_sentence: str) -> tuple[float, float]:
    fields = nmea_sentence.strip().split(',')
    sentence_type = fields[0].lstrip('$').upper()

    if sentence_type in ["GPRMC", "GNRMC"]:
        lat_str = fields[3]
        ns = fields[4]
        lon_str = fields[5]
        ew = fields[6]
    elif sentence_type in ["GPGGA", "GNGGA"]:
        lat_str = fields[2]
        ns = fields[3]
        lon_str = fields[4]
        ew = fields[5]
    elif sentence_type in ["GPGLL", "GNGLL"]:
        lat_str = fields[1]
        ns = fields[2]
        lon_str = fields[3]
        ew = fields[4]
    else:
        raise ValueError("Unsupported NMEA sentence type for coordinate conversion.")

    lat_decimal = nmea_to_decimal(lat_str, ns, is_lat=True)
    lon_decimal = nmea_to_decimal(lon_str, ew, is_lat=False)

    print(f"{lat_decimal:.6f}, {lon_decimal:.6f}")
    return lat_decimal, lon_decimal
