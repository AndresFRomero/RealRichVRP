# -*- coding: utf-8 -*-
"""
Modular Routing
TUL - Andrés F Romero
"""

# Importación de librerías
import services.globalFunctions as GF
from services.metaheuristic import ILS
from services.setPartitioning import SP
import services.config as config

import h3
import folium
import random
import time
from colorsys import hls_to_rgb

class LogisticRoutingPlanner:

    def __init__(self):
        self.excluded_packages = []
        self.pool_routes = []
        self.warm_start = []
        self.tM = dict()
        self.stats = {}

    def dataPreparation(self, packages, warehouse, fleet):
        if warehouse['name'] != 'Instance':
            packages.insert(0, {
                "uuid": "0",                   
                "db": "0,1440",               
                "h3r10": warehouse["h3r10"],        
                "products": []
            })
            for package in packages:
                GF.decodePackage(package, fleet)
                package['service_time'] = GF.serviceTime(package['total_weight'])
            GF.sortFleet(fleet)
            self.tM = GF.timeMatrix(packages, self.opt_parameters['warehouse_return'])
        else:   
            for package in packages:
                GF.decodePackage(package, fleet)
            GF.sortFleet(fleet)
            self.tM = GF.eucMatrix(packages, self.opt_parameters['warehouse_return'])

    def printSolution(self, selected_routes, packages, fleet, warehouse, plot: bool = False, filename: str = "") -> dict:
        
        start_time = time.time()
        ils = ILS(self.opt_parameters)
        solution = []
        X = []
        Y = []

        for idx, route in enumerate(selected_routes):
            route = self.pool_routes[route]["r"]
            route = ils.final2opt(route, packages, self.tM) # Final Route Improvement
            result = ils.routeEvaluation(route, packages, fleet, self.tM, False)
            packages_in_route = []
            for i in route:
                packages_in_route.append(packages[i]["uuid"])
                if (plot and warehouse['name'] != 'Instance'):
                    coors = h3.h3_to_geo(packages[i]["h3r10"])
                    try:
                        X[idx].append((coors[0], coors[1]))
                        Y[idx].append({"db": packages[i]["db"], "load": packages[i]["total_weight"]})
                    except:
                        X.append([(coors[0], coors[1])])
                        Y.append([ {"db": packages[i]["db"], "load": packages[i]["total_weight"]} ])

            result["packages"] = packages_in_route
            
            solution.append(result)
        
        for package in self.excluded_packages:
            result = package[1] # Package, RouteEval
            result["packages"] = [package[0]["uuid"]]
            solution.append(result)
        
        solution.sort(key=lambda x:x['minDep'], reverse=True ) 

        for package in solution:
            package['minDep'] = GF.realHour(package['minDep'])
            package['maxDep'] = GF.realHour(package['maxDep'])
            package['truck'] = package['truck'] + " ; " + package['minDep'] + " ; " + package['maxDep'] + " ; " + str(package['expectedTime'])
        
        if (plot and warehouse['name'] != 'Instance'):
            warehouse_coords = h3.h3_to_geo(warehouse["h3r10"])
            folium_map = folium.Map(location = warehouse_coords, tiles = 'cartodbpositron')
            folium.Marker(warehouse_coords, color = "black", popup="Warehouse").add_to(folium_map)
            usedPoints = set()
            for idx, route in enumerate(X):
                r,g,b = hls_to_rgb(random.uniform(0.0, 1.0), 0.8, 0.9)
                hex = '#%02x%02x%02x' % (int(r*255),int(g*255),int(b*255))
                for idx2, point in enumerate(route):
                    newPoint = list(point)
                    if point in usedPoints:            
                        newPoint[0] = newPoint[0] + random.uniform(-0.2,0.2)/500
                        newPoint[1] = newPoint[1] + random.uniform(-0.2,0.2)/500
                    usedPoints.add(point)
                    markerHTML = f"""
                        <div  style =  "background-color: {hex};
                            border-radius: 6px; 
                            opacity: 1;
                            border: 1px solid grey;
                            text-align: center;
                            color: black;">
                            {idx2+1}
                        </div>
                    """
                    packInfo = Y[idx][idx2]
                    popupHTML = f"""
                        <ul style = "padding-left:0;">
                            <li> Ruta: {idx +1} </li>
                            <li> Secuencia: {idx2 +1} </li>
                            <li> Peso [kg]: {packInfo["load"]} </li>
                            <li> Franja: {packInfo["db"]} </li>
                        </ul>
                    """
                    popup = folium.Popup(folium.IFrame(html=popupHTML, width=175, height= 100))
                    folium.Marker(newPoint, icon = folium.features.DivIcon(
                        icon_size=(18,18),
                        icon_anchor=(9,9),
                        html=markerHTML
                    ),popup=popupHTML).add_to(folium_map)
            
                #add lines
                folium.PolyLine(route, color=hex, weight=3.5, opacity=1).add_to(folium_map)

            folium_map.save("./maps/"+filename)

        self.stats["final_opti_time"] = round( (time.time()-start_time)/60 , 2 )

        return solution
  
    # =============================================================================
    # MAIN
    # =============================================================================
    def main(self, data, paint: bool = False, filename:str = "") -> dict:

        try:
            self.opt_parameters = config.warehouse_settings[data["warehouse"]["name"]]
        except:
            self.opt_parameters = {
                "fixed_cost": 0.6,
                "time_cost": 0.001,
                "distance_cost": 0,
                "stop_cost": 0.1,
                "excess_cost": 0.1,
                "penalty_cost": 0.1,
                "maximum_excess": 0.1,
                "maximum_penalties": 0,
                "release_weight": 0.1,
                'warehouse_return': False
            }
        
        start_time = time.time()
        self.dataPreparation(data['packages'], data['warehouse'], data['fleet'])
        self.stats["matrix_time"] = round( (time.time()-start_time)/60 , 2 )

        start_time = time.time()
        ils = ILS(self.opt_parameters)
        self.pool_routes, self.warm_start, self.excluded_packages = ils.main(data['packages'], data["fleet"], self.tM)
        del ils
        self.stats["ils_time"] = round( (time.time()-start_time)/60 , 2 )
        self.stats["pool_size"] = len(self.pool_routes)

        start_time = time.time()
        sp = SP()
        selected_routes = sp.main(self.pool_routes, data["fleet"], list(range(1, len(data['packages']))))
        del sp
        self.stats["sp_time"] = round( (time.time()-start_time)/60 , 2 )
        
        return self.printSolution(selected_routes, data['packages'], data["fleet"], data['warehouse'], paint, filename)