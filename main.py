import gps_log_generator as gps

def main() :
    latitude = 55.771298
    longitude = 49.136459
    start_speed = 50
    end_speed = 150
    step_speed = 10
    distance_coeff = 2
    heading = 55
    iterations = 70
    gps.generate(latitude, longitude, start_speed, end_speed, step_speed, distance_coeff, heading, iterations)

# parameters    
# latitude      : default moscow lat
# longitude     : default moscow lon
# start_speed   : default 10 km/h
# end_speed     : default 180 km/h
# step_speed    : default 5 km/h
# distance_coeff: default 1, (0.00005 * distance_coeff) degrees
# heading       : default 0°
# iterations    : default 50

if __name__ == "__main__":
    main()
