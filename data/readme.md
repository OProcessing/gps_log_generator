# GPS Log Data

## 1. Distance

### 1-1. Test Case
    GPS ALERT DISTANCE
    DB DISTANCE VOICE ALERT
    POI


### 1-2. How to USE 

1. 55.05, 37.00에 POI를 설정한다.
>
    start_lat = 55.050000
    start_lon = 37.000000
    end_lat = 55.050000
    end_lon = 37.000000
    start_speed = 40
    end_speed = 150
    step_speed = 10
    distance_coeff = 1
    heading = 90
    iterations = 100


2. 55.01, 37.00에서 gps log 시작하여 DB distance alert 확인한다.
>
    start_lat = 55.010000
    start_lon = 37.000000
    end_lat = 55.050000
    end_lon = 37.000000
    start_speed = 40
    end_speed = 150
    step_speed = 10
    distance_coeff = 0.5
    heading = 0
    iterations = 200


## 2. Speed

### 2-1. Test case
    SPEED STAMP
    MAXIMUM OVERSPEED
    OVER SPEED ALERT SOUNDS
    NO OVER SPEED ALERTS

### 2-2. How to USE 

1. start_speed와 end_speed, step_speed를 적절하게 설정하여 테스트한다.
>
    start_lat = 55.771298
    start_lon = 49.136459
    end_lat = 55.773277
    end_lon = 37.139285
    start_speed = 40
    end_speed = 180
    step_speed = 5
    distance_coeff = 1
    heading = 90
    iterations = 100


## 3. Backshot

### 3-1. Test case

    BACKSHOT OVERSPEED CONTROL
    
### 3-2. How to Use

1. 일정 시간 후 700m에서 Backshot alert 시작함.
>
    start_lat = 54.131027
    start_lon = 41.238703
    end_lat = 54.125934
    end_lon = 41.264014
    start_speed = 70
    end_speed = 150
    step_speed = 10
    distance_coeff = 1
    heading = 107
    iterations = 100