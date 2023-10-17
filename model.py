from src.sim import Sim_Window 
from src.agents import *
from src.helperfunctions import *
from src.turningkernel import *
import csv 
import os
import argparse as ap

# NOTE: handle argparsing
parser = ap.ArgumentParser(description="A script to generate an agent based model simulating paths generated by ants and their pheromone trails")

parser.add_argument("--agents", default=100, type=int, help="Max number of concurrent agents in the model")
parser.add_argument("--kernel", type=str, help="Selected turning kernel")
parser.add_argument("--max-time", default=1000, type=int, help="Max simulation time our model will run")
parser.add_argument("--multi", action='store_true', help="Toggle Multiprocess (on by default)")
parser.add_argument("--tao", default=10, type=int, help="Max trail length")
parser.add_argument("--board", default=255, type=int, help="Size of the board")
parser.add_argument("--debug",action='store_true', help='print debug messages to stderr')
parser.add_argument("--ssfreq", default=10, type=int, help="How frequently a ss should be taken")
args = parser.parse_args()

# Same Random
np.random.seed(0)

# NOTE: this is serving as a preamble of init classes / importing parameters
DEBUG:bool = args.debug
MAX_FIDELITY:float = 100
MIN_FIDELITY:float = 95
MAX_SATURATION:int = 30
MAX_PHEROMONE_STRENGTH:int = 20

# How often to Screen shot
ss_freq:int = args.ssfreq


tao = np.abs(args.tao)
agents = np.abs(args.agents)
max_time = args.max_time

board = np.zeros((args.board,args.board))

print(f"Starting model:\ntao: {tao}\nagents: {agents}\nmat time: {max_time}\nmulti: {args.multi}")

if __name__ == "__main__":

    wide_tk = TurningKernel( name="wide",
            values=[[.18,.18,.18],
                    [.18, 0, .18],
                    [.05, 0, .05]])
    narrow_tk = TurningKernel(name="narrow",
            values=[[.25,.3,.25],
                    [.1, 0 ,.1],
                    [.0, 0 ,.0]])
    flat_tk = TurningKernel(name="flat",
            values=[[1/8,1/8,1/8],
                    [1/8, 0 ,1/8],
                    [1/8,1/8,1/8]])
   
    match args.kernel:
        case "flat":
            TK = flat_tk
        case "narrow":
            TK = narrow_tk
        case "wide":
            TK = wide_tk
        case _:
            TK = TurningKernel()
    simulation = Sim_Window(
                        MAX_FIDELITY = 100,
                        MIN_FIDELITY = MIN_FIDELITY,
                        MAX_SATURATION = MAX_SATURATION,
                        MAX_PHEROMONE_STRENGTH = MAX_PHEROMONE_STRENGTH,
                        kernel = TK.name, 
                        tao=tao,
                        agents=agents,
                        window_size=(800,800),
                        grid_size=255,
                        max_time=max_time)
    # all_agents = np.array([Agent(tk=narrow_tk) for i in range(agents) ])
    all_agents:list[Agent] = []
    #all pheromones exist on their own board
    pheromone_concentration = board.copy()

    epoch = np.arange(start=1.0, stop=max_time+1) 
    
    all_pc = []

    #NOTE: Setting up multiprocessing
    processes = 6

    #NOTE: this will serve as our update loop. 
    for ctime in epoch:
        # Every cycle of our model is updated from within this loop
        if len(all_agents) < agents:
            
            all_agents.append(Agent(tk=TK, debug=args.debug,
                                    MAX_SATURATION=MAX_SATURATION,
                                    MIN_FIDELITY=MIN_FIDELITY,
                                    MAX_FIDELITY=MAX_FIDELITY))
        
        lost = 0
        
        nboard = board.copy()
        # NOTE: if more than 6 ants start multiprocessing
        if len(all_agents)>6 and args.multi:
            if DEBUG: print("MULTIPROCESSING!")
            list_chunks = list(split_list(all_agents,processes))
            with multiprocessing.Pool(processes=processes) as pool:
            # Perform computations on each chunk in parallel
                r = pool.starmap(process_section, [(len(board),pheromone_concentration, lc) for lc in list_chunks])
                
                # Flatten the results list
                results:list[Agent]       = [f for t in r for f in t[0]]
                xtmp:list[int]            = [f for t in r for f in t[1]]
                ytmp:list[int]            = [f for t in r for f in t[2]]
                lost:int                  = sum([t[3] for t in r])
                
            # Update the original list with the processed results
            
            nboard[xtmp,ytmp] = 1
            all_agents = results
            pheromone_concentration = simulation.updatePheromone(pheromone_concentration, xtmp, ytmp)
        else:
            # update all ants
            xtmp = [] 
            ytmp = []
            for ant in all_agents:
                _x,_y = ant.get_position()
                if _x < 1 or _x>len(board)-2 or _y <1 or _y > len(board)-2:
                    ant.reset()
                    _x,_y = ant.get_position()
                xtmp.append(_x) 
                ytmp.append(_y)
                if DEBUG: print(f"{_x},{_y}")
                nboard[_x][_y] = 1
                ant.update(pheromone_concentration)
                lost += ant.is_lost()
            
        
        if ctime %ss_freq == 0: 
            simulation.save_to_disc(int(ctime//ss_freq))
        #print(f"xtmp:{xtmp}\nytmp:{ytmp}") 
        
        pheromone_concentration =  simulation.updatePheromone(pheromone_concentration, xtmp, ytmp)
        simulation.update(np.multiply(pheromone_concentration, 255//tao), nboard)
        simulation.metrics(lost,ctime)
        simulation.write()
        all_pc.append(pheromone_concentration.copy()) 


    # NOTE: post simulation cleanup
    simulation.save_to_disc(extra="fstate")
    hf.save_figure(boardnorm(all_pc), dir=simulation.savedir, max=.1)
    rslts = calculate_statistics(execution_times)
    write_stats(rslts)
    simulation.close() 

