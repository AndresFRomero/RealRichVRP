import h3
import math
import time
import requests
import numpy as np
from math import floor

def linearTime(origin: str, destination: str, vel: float = 12) -> int:
    # Taking into account the world radius
    R = 6373

    lat1, lng1 = h3.h3_to_geo(origin)
    lat2, lng2 = h3.h3_to_geo(destination)

    lat1 = math.radians(lat1)
    lng1 = math.radians(lng1)
    lat2 = math.radians(lat2)
    lng2 = math.radians(lng2)

    dlng = lng2 - lng1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * \
        math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c  # Distance in km
    time = distance / vel * 60  # time in minutes
    time = min(60 + time/2.5, time)
    return int(time)


def realTime(origin: str, destination: str) -> int:
    # HereMaps Routing API consumer
    url = 'https://router.hereapi.com/v8/routes'

    lat1, lng1 = h3.h3_to_geo(origin)
    lat2, lng2 = h3.h3_to_geo(destination)

    departureTime = time.gmtime(time.time() + 24 * 60 * 60)
    departureTime = str(departureTime.tm_year).zfill(4) + '-' + str(departureTime.tm_mon).zfill(2) + \
        '-' + str(departureTime.tm_mday).zfill(2) + 'T08:00:00' + "-05:00"

    payload = {
        'transportMode': 'truck',
        'origin': str(lat1) + ',' + str(lng1),
        'destination': str(lat2) + ',' + str(lng2),
        'routingMode': 'fast',
        'return': 'summary',
        'departureTime': departureTime,
        'apiKey': '6pn8qyX-ME-3alod87qHZSO8DQyxdF2b8A72e1aa2PY'
    }

    response = requests.get(url, params=payload)
    response = response.json()
    # Time in min
    return int(response['routes'][0]['sections'][0]['summary']['duration'] / 60)

def realTimeMatrix(origins: list, destinations: list):

    geoOrigins = []
    for i in origins:
        lat,lng = h3.h3_to_geo(i)
        geoOrigins.append({
            "lat": lat,
            "lng": lng
        })
    
    geoDestinations = []
    for i in destinations:
        lat,lng = h3.h3_to_geo(i)
        geoDestinations.append({
            "lat": lat,
            "lng": lng
        })
    
    url = 'https://matrix.router.hereapi.com/v8/matrix'
    jsonData = {
        'origins': geoOrigins,
        'destinations': geoDestinations,
        'profile': 'truckFast',
        'regionDefinition': { "type" : 'world' }
    }
    queryParams = {
        "apiKey": "6pn8qyX-ME-3alod87qHZSO8DQyxdF2b8A72e1aa2PY",
        "async": 'false'
    }

    response = requests.post(url, json=jsonData, params=queryParams )
    response = response.json()["matrix"]["travelTimes"]
    response = [ int(round(item/60,0)) for item in response]
    # Time in min
    return response

def serviceTime(total_weight: float) -> int:
    if total_weight == 0:
        return 0
    else:
        x = (total_weight-3000)/1000
        return int(1/(1 + math.exp(-1.4*(x + 0.25)))*80 + 15)

def decodeProduct(product: str, fleet: dict) -> dict:
    max_length = 0
    max_width = 0
    max_height = 0

    # Length Cut
    for truck in fleet:
        if truck['length'] > max_length:
            max_length = truck['length']
        if truck['width'] > max_width:
            max_width = truck['width']
        if truck['height'] > max_height:
            max_height = truck['height']

    try:
        weight, length, width, height, q = [ float(element) for element in product.split(",")]
    except:
         weight, length, width, height, q = product['weight'], product['length'], product['width'], product['height'], product['q']
         
    return {
        "weight": weight,
        "length": min(length, max_length),
        "width": min(width, max_width),
        "height": min(height, max_height),
        "q": int(q)
    }


def decodePackage(package: dict, fleet: dict):
    total_weight = 0
    total_volume = 0
    max_length = 0
    max_width = 0
    max_height = 0

    for idx, product in enumerate(package['products']):
        package['products'][idx] = decodeProduct(product, fleet)

        total_weight += package['products'][idx]['weight']*package['products'][idx]['q']
        total_volume += package['products'][idx]['length'] * \
                        package['products'][idx]['width'] * \
                        package['products'][idx]['height'] * package['products'][idx]['q']

        if package['products'][idx]['length'] > max_length:
            max_length = package['products'][idx]['length']
        if package['products'][idx]['width'] > max_width:
            max_width = package['products'][idx]['width']
        if package['products'][idx]['height'] > max_height:
            max_height = package['products'][idx]['height']

    package['total_weight'] = total_weight
    package['total_volume'] = total_volume
    package['max_length'] = max_length
    package['max_width'] = max_width
    package['max_height'] = max_height
    package['start'], package['end'] = [ int(element) for element in package['db'].split(",") ]

def sortFleet(fleet: list):
    for truck in fleet:
        truck["volume"] = truck["length"] * truck["width"] * truck["height"] 
    fleet.sort(key = lambda x: x["cost"])

def timeMatrix(packages: list, warehouse_return: bool) -> dict:
    result = {}
    # Simetric Matrix, only one origin and multiple destinations
    for idx, a in enumerate(packages):
        origin = a['h3r10']
        destinations = packages[idx:]
        destinations = [ item['h3r10'] for item in destinations ]
        result[origin, origin] = 0
        try:
            # realTimes = [ linearTime(origin, i) for i in destinations ]
            realTimes = realTimeMatrix([origin], destinations)
            for idx2, time in enumerate(realTimes):
                result[origin, destinations[idx2]] = time
                result[destinations[idx2], origin] = time
        except:
            realTimes = [ linearTime(origin, i) for i in destinations ]
            for idx2, time in enumerate(realTimes):
                result[origin, destinations[idx2]] = time
                result[destinations[idx2], origin] = time

    if warehouse_return == False:
        for i in result:
            if i[1] == packages[0]['h3r10']:
                result[i] = 0
    
    return result  # Time in min


def eucMatrix(packages:list, warehouse_return: bool) -> dict:
    result = {}
    for idx, a in enumerate(packages):
        origin = a['h3r10']
        for idx, b in enumerate(packages):
            destination = b['h3r10']
            loc1 = np.array((a['lat'], a['lng']))
            loc2 = np.array((b['lat'], b['lng']))
            result[origin,destination] = round(np.linalg.norm(loc1-loc2),2)
    
    if warehouse_return == False:
        for i in result:
            if i[1] == packages[0]['h3r10']:
                result[i] = 0

    return result

def realHour(departure: float) ->str:
    r=round(departure)
    minutes=r%60
    hour=str(floor(r/60))
    minutes=("0","")[minutes>9]+str(minutes)
    return  hour + ":" +minutes

