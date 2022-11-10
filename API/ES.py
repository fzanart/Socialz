import logging
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from scipy.stats import qmc
from tqdm import tqdm
import random
from multiprocessing import Pool
from itertools import combinations

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO, datefmt='%d-%b-%y %H:%M:%S')

class evolutionary_strategy():

    def __init__(self, edge_list, cpus=4):
        self.edge_list = edge_list
        self.users = edge_list['source'].unique().tolist()
        self.repos = edge_list['target'].unique().tolist()
        self.cpus = cpus
        self.pool = Pool(self.cpus)
        self.event_types = edge_list['type'].unique()
        self.combinations = self.get_combinations()

    def get_combinations(self):
        # create all posible combination of events (type)
        # 1. Get the event types and the number of them.
        n = len(self.event_types)
        # 2. Evaluate all the possible combinations
        event_comb = []
        for i in range(1,n+1):
            comb = combinations(self.event_types,i)
            event_comb.extend(list(comb))
        # 3. Map, in a dict, a value to each (sorted names on) tuples (combinations)
        comb_dict = {}
        for event, value in zip(event_comb, list(range(1,len(event_comb)+1))):
            comb_dict[tuple(sorted(event))] = value

        return comb_dict

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
    
    def complete_edgelist(self, edge_list):
        # Add user-user FollowEvents based on cosine similarity
        
        # Remove followEvent if exists on the edge_list
        if (edge_list['type'].eq('FollowEvent')).any():
            edge_list = edge_list[~edge_list['type'].isin(['FollowEvent'])].reset_index(drop=True)

        # Build the adjacency matrix for user - repo (and repo - user) interactions.
        adj_matrix = pd.crosstab(edge_list['source'], edge_list['target']).astype(float)
        idx = adj_matrix.columns.union(adj_matrix.index)
        adj_matrix = adj_matrix.reindex(index = idx, columns=idx, fill_value=0.0) 
        adj_matrix.loc[self.users, self.users] = self.user_user_similarity(adj_matrix)
        
        # Create edge list from user-user similarity:
        user_user = adj_matrix.loc[self.users, self.users]
        G = nx.from_pandas_adjacency(user_user, create_using=nx.DiGraph())
        user_user = nx.to_pandas_edgelist(G)
        user_user['type'] = 'FollowEvent'
        user_user = user_user.drop(columns='weight')

        # Append user_user edge list to edge_list:
        edge_list = pd.concat([edge_list, user_user], ignore_index=True, axis=0)
        
        return edge_list

    def mutate(self, edge_list, sample):
        # divide sample into the number of edges to add/remove
        aux_1 = np.random.randint(0,sample+1)
        aux_2 = sample - aux_1
        add_node, delete_node = max(aux_1, aux_2), min(aux_1, aux_2)
        logging.debug(f'adding: {add_node}, deleting: {delete_node}')
        # select a node to alter
        node = np.random.choice(self.users)

        # Remove existing followEvent on the edge_list, and/or create a copy
        if (edge_list['type'].eq('FollowEvent')).any():
            el = edge_list[~edge_list['type'].isin(['FollowEvent'])].reset_index(drop=True).copy()
        else:
            # Create copy of edge_lis:
            el = edge_list.copy()

        # Create random new edges and add them to the edge list.
        for _ in range(add_node): 
            new_edge_user_repo = pd.DataFrame({'source':[node], 'target':[random.choice(self.repos)], 'type':[random.choice(self.event_types)]})
            el = pd.concat([el, new_edge_user_repo], ignore_index=True, axis=0)
        
        # Delete edges if delete_node > 0:
        if delete_node > 0:
            aux_el = None
            # Check that removing edges dont remove users or repos.
            logging.debug(f'entering while condition: ...')
            while aux_el is None or not len(aux_el['source'].unique()) == len(self.users) or not len(aux_el['target'].unique()) == len(self.repos):
            
                drop_idxs = np.random.choice(el.index, delete_node, replace=False)
                aux_el = el.drop(drop_idxs).reset_index(drop=True)
            
            el = aux_el

        # Add follow events to the new edge list
        el = self.complete_edgelist(el)

        return el
    
    def map_combinations(self, edge_list):
        
        # Map the corresponding value for each user involved on each combination of events.
        map_values = []
        for user in self.users:
            aux = edge_list[edge_list['source']==user]
            if (aux['type'].eq('FollowEvent')).any():
                aux = aux[~aux['type'].isin(['FollowEvent'])]
            events = tuple(sorted(aux['type'].unique()))
            map_values.append(self.combinations[events])

        return pd.DataFrame({'Users':self.users, 'Values':map_values}).set_index('Users')

    def graph_metrics(self, edge_list):

        # Evaluate Degree and Eigenvector centralities for each node in a Graph
        G = nx.from_pandas_edgelist(self.complete_edgelist(edge_list), create_using=nx.DiGraph)
        
        result = pd.DataFrame({'Centrality': nx.pagerank(G), 'Degree': {node:val for (node, val) in G.degree()}})

        # filter users, concatenate with mapped values
        result = result[result.index.str.startswith('u: ')]
        mapped_values = self.map_combinations(edge_list)
        result = pd.concat([result, mapped_values], axis=1, ignore_index=False)
        
        # Scale values
        for column in result:
            result[column] = result[column].apply(lambda x: (x - result[column].min())/(result[column].max() - result[column].min()))

        return result

    def objective(self, candidate):  
        candidate = self.graph_metrics(candidate)
        # Evaluate metrics in terms of star-discrepancy
        return qmc.discrepancy(candidate, method='L2-star',workers=-1)

    def es_plus(self, n_iter, mu, lam, A = 2, b = 0.5, progress_bar=True):
        logging.debug('evolutionary strategy begins...')
        
        best, best_eval = None, 1e+10
        n = self.edge_list.shape[0]
        prob = 1/n
        
        # calculate the number of children per parent
        n_children = int(lam / mu)
        
        # initial population
        population = list()
    
        for i in range(lam):
            candidate = self.edge_list.copy()       # copy the initial edge_list
            population.append(candidate)            # add to population

        # perform the search
        for epoch in tqdm(range(n_iter), disable=progress_bar):
            # sample from binomial distribution > 0
            if prob > 1: prob = 1 # set upper bound
            sample = np.random.binomial(n, prob)
            if sample < 1: sample = 1 # set lower bound           
            # evaluate the fitness for the population
            scores = self.pool.map(self.objective, population)
            # rank scores in ascending order
            ranks = np.argsort(np.argsort(scores))
            # select the indexes for the top mu ranked solutions, drop the worse results
            selected = [i for i,_ in enumerate(ranks) if ranks[i] < mu]
            # create offspring from parents
            offspring = list()
            for i in selected:
            # check if this parent is the best solution ever seen
                count = 0 # add a counter of successful candidates
                if scores[i] < best_eval:
                    best, best_eval, niter = population[i], scores[i], epoch
                    count += 1
                    logging.info(f'n_iter: {epoch}, score: {best_eval:.5f}, sample_size: {sample}')
                # keep the parent
                offspring.append(population[i])
                # create offspring for parent
                for _ in range(n_children):
                    child = self.mutate(population[i], sample)
                    offspring.append(child)
            # replace population with children
            population = offspring
            if count > 0: prob = prob*A #increase success prob when successful candidates were encountered
            else: prob = prob*b # decrease prob.
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
