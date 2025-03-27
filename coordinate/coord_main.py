import coord_cal as cc

def main() :

    nmea_rmc = "$GPRMC,115921.00,A,5546.03169,N,04907.50652,E,29.6976241900648,90,030124,,,A*42"
    cc.nmea_sentence_to_decimal(nmea_rmc)

    #nmea_gga = "$GPGGA,115921.00,5546.03169,N,04907.50652,E,1,08,1.1,100.0,M,0.0,M,,*5D"
    #cc.nmea_sentence_to_decimal(nmea_gga)

    #nmea_gll = "$GPGLL,5546.03169,N,04907.50652,E,115921.00,A,A*6D"
    #cc.nmea_sentence_to_decimal(nmea_gll)


if __name__ == "__main__":
    main()