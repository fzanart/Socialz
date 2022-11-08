import logging
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from scipy.stats import qmc
from tqdm import tqdm
import random
#from multiprocessing.pool import ThreadPool
from multiprocessing import Pool

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO, datefmt='%d-%b-%y %H:%M:%S')

class evolutionary_strategy():

    def __init__(self, edge_list, cpus=4):
        self.edge_list = edge_list
        self.users = edge_list['source'].unique().tolist()
        self.repos = edge_list['target'].unique().tolist()
        self.cpus = cpus
        #self.pool = ThreadPool(cpus)
        self.pool = Pool(self.cpus)

    def user_user_similarity(self, adj_matrix):
    
        # Evaluate user-user similarity:
        
        ## Get repo - user similarity (upper-right square):
        repo_user = adj_matrix.iloc[:len(self.repos),len(self.repos):]
        repo_user = repo_user/np.linalg.norm(repo_user,axis=0,keepdims=True)
        repo_user[np.isnan(repo_user)] = 0
        repo_user = np.dot(repo_user.transpose(),repo_user)

        ## Get user - repo similarity (lower-left square):
        user_repo = adj_matrix.iloc[len(self.repos):,:len(self.repos)]
        user_repo = user_repo/np.linalg.norm(user_repo,axis=1,keepdims=True)
        user_repo[np.isnan(user_repo)] = 0
        user_repo = np.dot(user_repo, user_repo.transpose())

        # Combine upper and lower triangles, keep 0 in the diagonal.
        user_user = np.triu(repo_user,1) + np.tril(user_repo,-1)

        return user_user
    
    def create_adjacency_matrix(self, edge_list):
        
        # Build the adjacency matrix for user - repo (and repo - user) interactions.
        
        adj_matrix = pd.crosstab(edge_list['source'], edge_list['target']).astype(float)
        idx = adj_matrix.columns.union(adj_matrix.index)
        adj_matrix = adj_matrix.reindex(index = idx, columns=idx, fill_value=0.0) 
        adj_matrix.loc[self.users, self.users] = self.user_user_similarity(adj_matrix)
        
        return adj_matrix

    def mutate(self, edge_list, node):

        # Create copy of edge_lis:
        el = edge_list.copy()

        # Create 1 to 10 random new edges and add them to the edge list.
        add = random.randint(1, 10)

        for _ in range(add): 
            new_edge_user_repo = pd.DataFrame({'source':[node], 'target':[random.choice(self.repos)]})
            el = pd.concat([el, new_edge_user_repo], ignore_index=True, axis=0)
        
        # Else, delete 1 to 5 edges if random == 0 with 25% prob.
        if np.random.choice([0,1], p=[0.25,0.75]) == 0:
            remove = np.random.choice([1,2,3,4,5])
            
            aux_el = None
            # Check that removing edges dont remove users or repos.
            while aux_el is None or not len(aux_el['source'].unique()) == len(self.users) or not len(aux_el['target'].unique()) == len(self.repos):
            
                drop_idxs = np.random.choice(el.index, remove, replace=False)
                aux_el = el.drop(drop_idxs).reset_index(drop=True)
            
            el = aux_el

        return el

    def graph_metrics(self, edge_list):
    
        # Evaluate Degree and Eigenvector centralities for each node in a Graph
        G = nx.from_pandas_adjacency(self.create_adjacency_matrix(edge_list), create_using=nx.DiGraph)
        
        result = pd.DataFrame({'Centrality': nx.pagerank(G), 'Degree': {node:val for (node, val) in G.degree()}})

        # filter users
        result = result[result.index.str.startswith('u: ')]
        
        # Scale values
        for column in result:
            result[column] = result[column].apply(lambda x: (x - result[column].min())/(result[column].max() - result[column].min()))

        return result

    def objective(self, candidate):  
        candidate = self.graph_metrics(candidate)
        # Evaluate metrics in terms of star-discrepancy
        return qmc.discrepancy(candidate, method='L2-star',workers=-1)

    def es_plus(self, n_iter, mu, lam, progress_bar=True):
        logging.debug('evolutionary strategy begins...')
        
        best, best_eval = None, 1e+10
        
        # calculate the number of children per parent
        n_children = int(lam / mu)
        
        # initial population
        population = list()
    
        for i in range(lam):
            candidate = self.edge_list.copy()       # copy the initial edge_list
            population.append(candidate)            # add to population

        # perform the search
        for epoch in tqdm(range(n_iter), disable=progress_bar):
            # evaluate the fitness for the population
            #scores = [self.objective(candidate) for candidate in population]
            scores = self.pool.map(self.objective, population)
            # rank scores in ascending order
            ranks = np.argsort(np.argsort(scores))
            # select the indexes for the top mu ranked solutions, drop the worse results
            selected = [i for i,_ in enumerate(ranks) if ranks[i] < mu]
            # create offspring from parents
            offspring = list()
            for i in selected:
            # check if this parent is the best solution ever seen
                if scores[i] < best_eval:
                    best, best_eval, niter = population[i], scores[i], epoch
                    logging.info('n_iter: %d, score: %.5f' % (epoch, best_eval))
            
                # keep the parent
                offspring.append(population[i])

                # create offspring for parent
                for j in range(n_children):
                    sample = np.random.choice(self.users)
                    child = self.mutate(population[i], sample)
                    offspring.append(child)

            # replace population with children
            population = offspring
        logging.debug('evolutionary strategy ended')
        return niter, best, best_eval

    # Without the following two formulas, you get NotImplementedError 
    # see ref: https://stackoverflow.com/questions/25382455/python-notimplementederror-pool-objects-cannot-be-passed-between-processes
    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['pool']
        return self_dict

    def __setstate__(self, state):
        self.__dict__.update(state)
