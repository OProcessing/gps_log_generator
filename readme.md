### GPS NMEA Log Generator

## How to Use

    latitude = 55.771298      # Starting latitude (default: Moscow latitude)
    longitude = 49.136459     # Starting longitude (default: Moscow longitude)
    start_speed = 50          # Starting speed in km/h (default: 10 km/h)
    end_speed = 150           # Ending speed in km/h (default: 180 km/h)
    step_speed = 5            # Speed increment per iteration (default: 5 km/h)
    distance_coeff = 2        # Multiplier for step distance in degrees (default: 1)
    heading = 55              # Heading (direction) in degrees (default: 0째)
    iterations = 70           # Number of iterations for generating log points (default: 50)

    eg.
    # Generates GPS log with speeds ranging from 50 to 100 km/h in 5 km/h increments for 50 iterations
    gps.generate(start_speed=50, end_speed=100, step_speed=5) 

    # Generates GPS log with speeds ranging from 20 to 70 km/h in 10 km/h increments for 5 iterations
    gps.generate(start_speed=20, end_speed=120, step_speed=10, iterations=5) 

    # Generates GPS log in moscow, 10-180 km/h, 5 km/h step, head to north
    gps.generate() 
