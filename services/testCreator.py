"""
Test Creator New Format
"""

import pandas as pd
import json
import h3

problems = pd.read_csv("../data/problems.csv").to_dict(orient='index')

days = [28]

trucks = pd.read_csv('../data/truckTypes.csv')
trucks = trucks.to_dict(orient='index')

warehouses = pd.read_csv('../data/warehouses.csv', index_col='NAME')
warehouses = warehouses.to_dict(orient='index')

# Function
def timeConversion(strTime: str):
        h, m, s = strTime.split(":")
        h = int(h)
        m = int(m)
        s = int(s)
        return int(h * 60 + m + s / 60)

for warehouse in warehouses:
    for day in days:
        fleet = []
        for t in trucks:
            if (trucks[t]['WAREHOUSE'] == warehouse):
                fleet.append({
                    'name': trucks[t]['TRUCK'],
                    'weight': trucks[t]['WEIGHT'],
                    'time':  trucks[t]['ROUTE_TIME'],
                    'length': trucks[t]['LENGTH']*100,
                    'width': trucks[t]['WIDTH']*100,
                    'height': trucks[t]['HEIGHT']*100,
                    'cost': trucks[t]['FIXED_COST'],
                    'quantity': 100
                })
        result = {
            'fleet': fleet,
            'warehouse': {
                'uuid': warehouses[warehouse]['UUID'],
                'name': warehouse,
                'h3r10': h3.geo_to_h3(warehouses[warehouse]['LAT'], warehouses[warehouse]['LNG'], 10)
            },
            'packages': {}
        }
        for i in problems:
            if (problems[i]['WAREHOUSE'] == warehouse and problems[i]['DAY_SCHEDULE'] == day):
                pack = problems[i]
                try:
                    result['packages'][pack['UUID']]['products'].append(pack['PRODUCT'])
                except:
                    result['packages'][pack['UUID']] = {
                        "uuid":str(pack['UUID']),
                        "db": str(timeConversion(pack['START']))+','+str(timeConversion(pack['END'])),
                        "h3r10": h3.geo_to_h3(pack['LAT'], pack['LNG'], 10),
                        "products": [
                            pack['PRODUCT']
                        ]
                    }
        result['packages'] = [
            result['packages'][i] for i in result['packages']
        ]

        with open("../tests/"+warehouse+''+str(day)+'.json', "w") as fp:
                json.dump(result, fp)
