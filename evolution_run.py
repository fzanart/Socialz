#%%
import argparse
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from API.ES_src import evolutionary_strategy

def main():

    save_dir = './Datasets'
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    parser = argparse.ArgumentParser()

    parser.add_argument('--input_file_path', type=str)
    parser.add_argument('--output_filename', type=str)
    parser.add_argument('--multiprocessing_units', type=int, default=1)
    parser.add_argument('--n_iter', type=int, default=1000)
    parser.add_argument('--mu', type=int, default=1)
    parser.add_argument('--lam', type=int, default=20)
    parser.add_argument('--A', type=float, default=2)
    parser.add_argument('--b', type=float, default=0.5)
    parser.add_argument('--disable_progress_bar', type=bool, default=False)
   
    args = parser.parse_args()

    ds = pd.read_csv(args.input_file_path)
    es = evolutionary_strategy(ds, cpus=args.multiprocessing_units)
    niter, best, best_eval = es.es_plus(args.n_iter, args.mu, args.lam, args.A, args.b, args.disable_progress_bar)
    
    save_path = os.path.splitext(args.output_filename)[0] + '.csv'
    
    es.complete_edgelist(best).to_csv(save_path, index=False)

# TODO: read logfile and plot convergence curve

if __name__ == '__main__':
    main()