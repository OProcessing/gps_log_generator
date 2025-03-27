import gps_log_generator as gps

def main() :
    start_lat = 55.751244
    start_lon = 37.618423
    end_lat = 55.751244
    end_lon = 37.618423
    start_speed = 10
    end_speed = 180
    step_speed = 5
    distance_coeff = 1
    heading = 0
    iterations = 100
    

    gps.generate(start_lat, start_lon, end_lat, end_lon, start_speed, end_speed, step_speed, distance_coeff, heading, iterations)

# parameters    
# latitude      : default moscow lat
# longitude     : default moscow lon
# start_speed   : default 10 km/h
# end_speed     : default 180 km/h
# step_speed    : default 5 km/h
# distance_coeff: default 1, (0.00005 * distance_coeff) degrees
# heading       : default 0°
# iterations    : default 100

if __name__ == "__main__":
    main()
