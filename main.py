from services.logisticRoutingPlanner import LogisticRoutingPlanner

import pandas as pd
import json
import time
from os import walk

testLocation = './tests/CVRP/'
filenames = next(walk(testLocation), (None, None, []))[2] 
performance_analysis = {}
for request in filenames:
    with open(testLocation + request, "r") as fp:
        data = json.load(fp)

    stats = {
        "nPackages" : len(data["packages"]),
        "warehouse" : data["warehouse"]
    }
    print("Truck Routing Worker Start ", request,  stats)

    filename = request.replace('.json', '.html')
    start= time.time()
    LRP = LogisticRoutingPlanner()
    result = LRP.main(data, True, filename)
    stats = LRP.stats
    stats["total_time"] = round((time.time() - start) / 60, 2)
    
    trucks = {}
    for i in result:
        try:
            trucks[i["truck"].split(" ; ")[0]] += 1
        except:
            trucks[i["truck"].split(" ; ")[0]] = 1

    performance = {
        "warehouse": data['warehouse']['name'],
        "nPacks": sum([len(i['packages']) for i in result]),
        "trucks": trucks,
        "total_weigth": sum([i['load'] for i in result]),
        "expected_cost" : sum([i['expectedCost'] for i in result]),
        "expected_time": sum([i['expectedTime'] for i in result]),
        "n_routes": len(result),
        "time_stats": stats
    }
    print('---Objective Fun---', performance['expected_cost'], '\n')

    performance_analysis[request] = { 'summary': performance, 'result': result }

with open('cvrp_results.json', 'w') as fp:
    json.dump(performance_analysis, fp)