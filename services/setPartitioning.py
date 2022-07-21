# Libraries
from pyomo.environ import ConcreteModel, Var, Objective, ConstraintList, SolverFactory, Binary, Integers

class SP:

    def __init__(self) -> None:
        pass

    def setPartitioning(self, pool_routes, fleet, nodes):

        model = ConcreteModel()
        # SETS
        V = list(range(len(fleet)))             # Set of vehicles types
        R = list(range(len(pool_routes)))       # Set of routes
        N = nodes                               # Set of nodes
        
        # PARAMETERS
        alpha = { (r,n): 1 if n in pool_routes[r]['r'] else 0 for r in R for n in N}
        cost = { r: pool_routes[r]['c'] for r in R }
        asignation = { v: set() for v in V }
        for idx, route in enumerate(pool_routes):
            asignation[route['t']].add(idx)
            
        cap = { idx:truck['quantity'] for idx, truck in enumerate(fleet) }
        bigM = { idx:truck['cost']*100 for idx, truck in enumerate(fleet) }

        # DECISION
        model.x = Var(R, domain = Binary)   # Fleet
        model.h = Var(V, domain = Integers,  bounds = (0, None))   # Holguras
        
        # OBJECTIVE
        model.Cost = Objective(
            expr = sum( [cost[r]*model.x[r] for r in R ]) + sum( [bigM[v]*model.h[v] for v in V]),
                    sense = 1 )
        
        # CONSTRAINTS
        # All nodes have to be visited
        model.visits = ConstraintList()
        for n in N:
            model.visits.add( sum( [ model.x[r]*alpha[r,n] for r in R ] ) == 1 )
        
        # Fleet or Slack
        model.fleet = ConstraintList()
        for v in V:
            model.fleet.add( sum([ model.x[r] for r in asignation[v]]) - model.h[v] <= cap[v] )
        
        solver = SolverFactory('cbc')
        solver.solve(model, tee = False)
        
        # model.display()

        usedRoutes = set()
        for r in R:
            if model.x[r]() > 0.8:
                usedRoutes.add(r)

        return usedRoutes

    def main(self, pool_routes, fleet, nodes) -> dict:
        return self.setPartitioning(pool_routes, fleet, nodes)