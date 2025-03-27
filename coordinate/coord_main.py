import coord_cal as cc

def main() :

    nmea_rmc = "$GPRMC"
    cc.nmea_sentence_to_decimal(nmea_rmc)

    #nmea_gga = "$GPGGA"
    #cc.nmea_sentence_to_decimal(nmea_gga)

    #nmea_gll = "$GPGLL"
    #cc.nmea_sentence_to_decimal(nmea_gll)


if __name__ == "__main__":
    main()