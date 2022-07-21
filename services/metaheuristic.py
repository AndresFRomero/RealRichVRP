# Libraries
import copy
import numpy as np
import services.globalFunctions as GF

class ILS:

    def __init__(self, opt_parameters) -> None:

        # Optimization parameters -> Objective Function
        self.depot_idx = 0
        self.fC = opt_parameters["fixed_cost"]
        self.tC = opt_parameters["time_cost"]
        self.dC = opt_parameters["distance_cost"]
        self.sC = opt_parameters["stop_cost"]
        self.eC = opt_parameters["excess_cost"]
        self.pC = opt_parameters["penalty_cost"]
        self.max_e = opt_parameters["maximum_excess"]
        self.max_p = opt_parameters["maximum_penalties"]
        self.rW = opt_parameters["release_weight"]

        # created data
        self.excluded_packages = []
        self.infact_packages = [] # Excluded Packages due to infactibilities
        self.warm_start = []
        self.arc_indexes = []
        self.pool_routes = {}

    def tsp(self, packages, tM) -> list:
        # Sets initialization
        visited = set([self.depot_idx])
        unvisited = set([idx for idx, i in enumerate(packages) if idx != self.depot_idx])

        # Route initialization
        route = [self.depot_idx]

        # Algorithm complexity O(logN); N: nodes (packages)
        while len(unvisited) > 0:
            # Solution initialization
            nearest = float("inf")
            nextnode = "-1"

            for j in unvisited:
                origin = packages[route[-1]]["h3r10"]
                destination = packages[j]["h3r10"]
                test = tM[origin, destination]
                if test < nearest:
                    nearest = test
                    nextnode = j

            route.append(nextnode)
            visited.add(nextnode)
            unvisited.discard(nextnode)
        
        return route
    
    def simpleStats(self, route: list, packages, tM) -> float:
        
        route2 = list(copy.deepcopy(route))
        route2.append(0)

        # Results Init
        load = 0
        volume = 0
        max_length = 0
        max_width = 0
        max_height =0

        for i in route:
            load += packages[i]['total_weight']
            volume += packages[i]['total_volume']
            max_length = max(max_length, packages[i]['max_length'])
            max_width = max(max_width, packages[i]['max_width'])
            max_height = max(max_height, packages[i]['max_height'])

        origin = packages[self.depot_idx]
        clients = 0

        # DB variables
        time = 0
        opTime = 0
        arrive = 0
        attention = 0
        waits = 0
        holg = 0
        penalties = 0
        prevST = 0
        max_departure = 1440
        
        leftLoad = load

        for i in route2:
            # Time calculations
            destination = packages[i]

            timePath = tM[origin["h3r10"], destination["h3r10"]]
            timePath = timePath*(1+leftLoad/load*self.rW)
            leftLoad -= packages[i]['total_weight']
            opTime += timePath + prevST

            if timePath < 1 and origin["start"] <= destination["start"]:
                start = 0
                end = 1440
            else:
                start = destination["start"] #rango de entrega
                end = destination["end"]
            
            arrive = attention + prevST + timePath 
            attention = max(arrive, start) 
            waits = waits + max(0, attention - arrive)
            holg = max(0, end - attention) 
            if attention > end:
                penalties += 1 
            max_departure = min(max_departure, waits + holg) 
            
            clients += 1
            prevST = destination["service_time"]

            origin = destination
        
        min_departure = min(waits, max_departure)
        time = attention - min_departure + prevST
        opTime += prevST
        deadTime = time - opTime

        return load, volume, max_length, max_width, max_height, opTime, deadTime, clients, penalties, min_departure, max_departure

    def routeEvaluation(self, route:list, packages, fleet, tM, summary: bool)-> dict:
        # Se inicializa el resultado
        posible = False
        cost = -1

        # Simple route stats
        load, volume, max_length, max_width, max_height, opTime, deadTime, clients, penalties, minDep, maxDep = self.simpleStats(route, packages, tM)
        time = opTime + deadTime
        for t, truck in enumerate(fleet):
            # Weight excess restriction fixed in 10%
            excessW = max(0,  load - truck['weight'])
            maxExcessW = truck['weight']*self.max_e

            EW = excessW > 5

            # Simple stats validator in the actual truck
            if (excessW <= maxExcessW
                and max_length <= truck['length']
                and max_width <= truck["width"]
                and max_height <= truck["height"]
                and volume <= truck['volume']
                and penalties <= self.max_p):
                
                # Time validator
                if (time <= truck['time']):

                    posible = True # In this point all restrictions pass
                    cost = truck['cost']*(self.fC + self.eC*EW+ self.pC*penalties+ self.sC*clients + opTime*self.tC)
                    
                    if load == 0:
                        load = 1
                    if summary:
                        return {'c': cost, 't': t, 'wc': cost/load} 
                    else:
                        return {'expectedCost': round(cost,2), 'expectedTime': round(time,2), 'truck': truck['name'],'load': load, 'minDep':minDep, 'maxDep': maxDep}
                    
            if (truck == fleet[-1] and posible == False):
                if summary:
                    return False
                else:
                    return (False, {'expectedCost': round(cost,2), 'expectedTime': round(time,2), 'truck': 'Infac','load': load, 'minDep':minDep, 'maxDep': maxDep})
            else:
                continue

        return False
    
    def preSolver(self, packages, fleet, tM):
        for idx, package in enumerate(packages):
            if idx != 0:
                route = [idx]
                result = self.routeEvaluation(route, packages, fleet, tM, False)
                try:
                    if result[0] == False:
                        self.excluded_packages.append((package, result[1]))
                except:
                    pass
        for i in self.excluded_packages:
            packages.remove(i[0])

    def assignInfac(self, fleet, packages):
        
        i = len(fleet)-1
        self.excluded_packages.sort(key= lambda x: x[1]['load'],reverse=True )

        for excluded in self.excluded_packages:
            fleet[i]['quantity']-=1
            excluded[1]['truck']= fleet[i]['name']+ ' Infac'   
            self.infact_packages.append(excluded)
            if fleet[i]['quantity']==0 and len(fleet)>1:
                del fleet[i]
                for package in packages:
                    GF.decodePackage(package, fleet)
                i -= 1
        self.excluded_packages=[]

    def simpleCost(self, route: list, packages, tM) -> float:
        node = self.depot_idx
        time = 0
        for i in route:
            time += tM[packages[node]["h3r10"], packages[i]["h3r10"]]
            node = i
        return time

    def _2optSwap(self, route: list, i: int, k: int) -> list:
        firstPart = route[0:i]
        secondPart = route[i:k + 1]
        thirdPart = route[k + 1:len(route)]
        return firstPart + secondPart[::-1] + thirdPart
    
    def simple2opt(self, bigRoute: list, packages, tM) -> list:

        n = len(bigRoute) # Nodes

        # Solution Initialization
        route = bigRoute
        bestRoute = bigRoute
        bestCost = self.simpleCost(bestRoute, packages, tM)

        improvement = True
        while improvement == True:
            improvement = False
            for i in range(1, n - 1):
                for j in range(i + 1, n):
                    newRoute = self._2optSwap(route, i, j)
                    newCost = self.simpleCost(newRoute, packages, tM)

                    if newCost < bestCost:
                        bestRoute = newRoute
                        bestCost = newCost
                        improvement = True

                route = bestRoute

        return bestRoute

    def final2opt(self, finalRoute: list, packages, tM):
        n = len(finalRoute) # Nodes

        # Solution Initialization
        route = finalRoute
        bestRoute = finalRoute
        initialRouteStats = self.simpleStats(route, packages, tM)
        opTime, penalties = initialRouteStats[5], initialRouteStats[8]
        bestCost = opTime

        improvement = True
        while improvement == True:
            improvement = False
            for i in range(0, n - 1):
                for j in range(i + 1, n):
                    newRoute = self._2optSwap(route, i, j)
                    routeStats = self.simpleStats(newRoute, packages, tM)
                    newOpTime, newPenalties = routeStats[5], routeStats[8]
                    if newPenalties <= penalties:
                        newCost = newOpTime
                    else:
                        newCost = bestCost

                    if newCost < bestCost:
                        bestRoute = newRoute
                        bestCost = newCost
                        improvement = True

                route = bestRoute

        return bestRoute

    
    def splitAlgorithm(self, route: list, packages, fleet, tM) -> list:
        arcs = []
        n = len(route)

        # All nodes can be the origin of a subtour
        for i in range(n - 1):
            # Consecutive nodes
            for j in range(i + 1, n):
                testRoute = route[i + 1:j + 1]
                
                # First check the poolRoutes dictionary in order to save time
                if (tuple(testRoute) in self.pool_routes):
                        subRoute = self.pool_routes[tuple(testRoute)]
                else:
                    subRoute = self.routeEvaluation(testRoute, packages, fleet, tM, True)
                    self.pool_routes[tuple(testRoute)] = subRoute

                # Only posible arcs are created
                if type(subRoute) == bool:
                    break
                else:
                    arcs.append([route[i], route[j], subRoute['c']])
        return arcs

    def bellmanFord(self, arcs: list, route: list) -> dict:

        solution = {}
        # BF initialization
        solution = {i: [self.depot_idx, float('inf')] for i in route if i != self.depot_idx}
        solution[self.depot_idx] = [self.depot_idx, 0]

        # One iteration O(n)
        for arc in arcs:
            dv = solution[arc[1]][1]
            du = solution[arc[0]][1]
            edge = arc[2]

            test = du + edge # Edge is only the integer cost
            if dv > test:
                solution[arc[1]] = [arc[0], test]

        return solution  # Predecessor, Cost
    
    def _2opt(self, bigRoute: list, packages, fleet, tM) -> list:

        n = len(bigRoute) # Nodes

        # Solution Initialization
        route = bigRoute
        bestRoute = bigRoute
        bestArcs = self.splitAlgorithm(bestRoute, packages, fleet, tM)
        bestSolution = self.bellmanFord(bestArcs, bestRoute)
        bestCost = bestSolution[bestRoute[-1]][1]

        iterC = 1 # Iteration counter

        improvement = True
        while improvement == True:
            improvement = False

            for i in range(1, n - 1):
                if iterC > self.max_iter:
                    improvement = False
                    break

                for j in range(i + 1, min(n, i + 1 + self.depth)):
                    if iterC > self.max_iter:
                        improvement = False
                        break

                    # Swap and cost
                    newRoute = self._2optSwap(route, i, j)
                    newArcs = self.splitAlgorithm(newRoute, packages, fleet, tM)
                    newSolution = self.bellmanFord(newArcs, newRoute)
                    newCost = newSolution[newRoute[-1]][1]
                    
                    # NewCost Evaluation
                    if newCost < bestCost*0.99:
                        bestRoute = newRoute
                        bestArcs = newArcs
                        bestSolution = newSolution
                        bestCost = newCost
                        improvement = True
                        break

                iterC += 1
                route = bestRoute
        
        last = bestRoute[-1]
        prev = -1
        rta = []
        arc_indexes = []
        
        while prev !=0:
            prev = bestSolution[last][0]
            for arc in bestArcs:
                origin = arc[0]
                destination = arc[1]
                orIndex = bestRoute.index(origin)
                dsIndex = bestRoute.index(destination)
                arc_indexes.append(tuple(route[orIndex+1:dsIndex+1]))
                if (origin == prev and destination == last):
                    rta.append(tuple(route[orIndex+1:dsIndex+1]))
            last = prev

        return rta, arc_indexes
    
    def reducePool(self, fleet):

        reduced_pool = []
        new_warm = []
        columns = dict()

        wCostsPerT = { idx: [] for idx in range(len(fleet))}
        for i in self.pool_routes:
            if self.pool_routes[i]!=False:
                try:
                    if self.pool_routes[i]["c"] < columns[frozenset(i)]:
                        columns[frozenset(i)] = self.pool_routes[i]
                        columns[frozenset(i)]["order"] = i
                    else:
                        pass
                except:
                    columns[frozenset(i)] = self.pool_routes[i]
                    columns[frozenset(i)]["order"] = i
                    wCostsPerT[self.pool_routes[i]["t"]].append(self.pool_routes[i]["wc"])

        self.pool_routes = columns

        totalFleet = max(1, sum( [ i["quantity"] for i in fleet ]))
        reducedPoolSize = 2000
        percentileP = {}
        
        for idx, i in enumerate(fleet):
            value = min(100, reducedPoolSize * i["quantity"]/totalFleet / (len(wCostsPerT[idx])+1) * 100)
            try:
                percentileP[idx] = np.percentile( wCostsPerT[idx], value )
            except:
                percentileP[idx] = float('inf')

        self.warm_start = [ frozenset(i) for i in self.warm_start ]
        self.arc_indexes = [ frozenset(i) for i in self.arc_indexes ]

        for i in self.pool_routes:
            if (i in self.warm_start) or (i in self.arc_indexes):
                reduced_pool.append({ 'r': self.pool_routes[i]["order"], 'c': self.pool_routes[i]['c'], 't': self.pool_routes[i]['t']})
                new_warm.append(i)
            elif ( self.pool_routes[i]['wc'] <= percentileP[self.pool_routes[i]['t']] ):
                reduced_pool.append({ 'r': self.pool_routes[i]["order"], 'c': self.pool_routes[i]['c'], 't': self.pool_routes[i]['t']})
            else:
                pass

        self.warm_start = new_warm
        self.pool_routes = reduced_pool

    def main(self, packages, fleet, tM) -> dict:

        self.max_iter = len(packages) * 50
        self.depth = 15
        
        self.preSolver(packages, fleet, tM)
        while len(self.excluded_packages)>0:
            self.assignInfac(fleet, packages)
            self.preSolver(packages, fleet, tM)

        bigRoute = self.tsp(packages, tM)
        bigRoute = self.simple2opt(bigRoute, packages, tM)
        self.warm_start, self.arc_indexes = self._2opt(bigRoute, packages, fleet, tM)
        self.reducePool(fleet)

        return self.pool_routes, self.warm_start, self.infact_packages
