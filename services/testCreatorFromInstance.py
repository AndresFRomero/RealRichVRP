import json
from os import walk

filenames = next(walk("../data/instances"), (None, None, []))[2] 
#filenames = ['A-n32-k5.vrp']
for file in filenames:
    with open("../data/instances/" + file, 'r') as fp:
        problem = { 'packages':[] , 'warehouse': {'name': 'Instance'}}
        n = 1
        for line in fp:

            line = line.rstrip('\n')
            if n < 7:
                line=line.split(" : ")
                try:
                    value = float(line[1])
                except:
                    value = line[1]
                problem[line[0]] = value

            elif(n > 7 and n <= 7+problem['DIMENSION']):
                line=line.split(" ")
                while True:
                    try:
                        line.remove('')
                    except:
                        break
                problem['packages'].append(
                    {
                        'uuid': int(line[0]),
                        'h3r10': int(line[0]),
                        'lat': float(line[1]),
                        'lng': float(line[2]),
                        'service_time': 0,
                        'db': "0,1440"
                    }
                )

            elif (n > 8 + problem['DIMENSION'] and n <= 8 + problem['DIMENSION']*2):
                line=line.split(" ")
                while True:
                    try:
                        line.remove('')
                    except:
                        break
                problem['packages'][int(line[0])-1]['products'] = [str(float(line[1])) + ",1,1,1,1"]
            else:
                pass
            n += 1
        fp.close()
    
    try:
        k = float(problem["NAME"].split('k')[1])
    except:
        k = 100
    problem['fleet'] = [
        {
            "name": "Instance CVRP",
            "weight": problem["CAPACITY"],
            "time": 1440,
            "length": 100,
            "width": 100,
            "height": 100,
            "cost": 1,
            "quantity": k
        }
    ]

    with open("../tests/"+problem['NAME']+'.json', "w") as fp:
        json.dump(problem, fp)
