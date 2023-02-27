import logging
import pandas as pd
import numpy as np
import graph_tool.all as gt
from scipy.stats import qmc
from tqdm import tqdm
import random
from multiprocessing import Pool
from itertools import combinations
import time

logging.basicConfig(filename='logfile_gt.log',
                    filemode='w', #open for exclusive creation, failing if the file already exists.
                    datefmt='%H:%M:%S,uuu',#'%d-%b-%y %H:%M:%S',
                    level=logging.INFO,
                    format='{%(message)s},')
class evolutionary_strategy():

    def __init__(self, edge_list, cpus=4):
        self.iter_n = 0
        self.edge_list = edge_list
        self.users = edge_list['source'].unique().tolist()
        self.repos = edge_list['target'].unique().tolist()
        self.cpus = cpus
        self.pool = Pool(self.cpus)
        self.event_types = edge_list['type'].unique().tolist()
        self.combinations = self.get_combinations()

    def get_combinations(self):
        st = time.time()
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
        et = time.time()
        logging.debug(f'"def":"get_combinations", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return comb_dict

    def user_user_similarity(self, adj_matrix):
        st = time.time()
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
        et = time.time()
        logging.debug(f'"def":"user_user_similarity", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return user_user

    def adjmatrix_to_edgelist(self, adj_matrix):
        st = time.time()
        #Transform an adjacency matrix to edge list
        sources, targets = np.nonzero(adj_matrix.to_numpy())
        adj_matrix = pd.DataFrame({'source':list(map(self.users.__getitem__, sources)), 'target':list(map(self.users.__getitem__, targets))})
        et = time.time()
        logging.debug(f'"def":"adjmatrix_to_edgelist", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return adj_matrix
    
    
    def complete_edgelist(self, edge_list):
        st = time.time()
        # Add user-user FollowEvents based on cosine similarity
        # Remove followEvent if exists on the edge_list
        edge_list = edge_list.loc[edge_list['type'] != 'FollowEvent'].reset_index(drop=True)
        
        # Build the adjacency matrix for user - repo (and repo - user) interactions.
        adj_matrix = pd.crosstab(edge_list['source'], edge_list['target']).astype(float)
        idx = adj_matrix.columns.union(adj_matrix.index)
        adj_matrix = adj_matrix.reindex(index = idx, columns=idx, fill_value=0.0)
        et = time.time()
        adj_matrix.loc[self.users, self.users] = self.user_user_similarity(adj_matrix)
        
        # Create edge list from user-user similarity:
        user_user = adj_matrix.loc[self.users, self.users]
        user_user = self.adjmatrix_to_edgelist(user_user)
        t1 = et - st
        st = time.time()
        user_user['type'] = 'FollowEvent'
        
        # Append user_user edge list to edge_list:
        edge_list = pd.concat([edge_list, user_user], ignore_index=True, axis=0)
        et = time.time()
        logging.debug(f'"def":"complete_edgelist", "elapsed_time":"{et-st+t1}", "iter":"{self.iter_n}"')
        return edge_list

    def mutate(self, edge_list, sample):
        st = time.time()
        # divide sample into the number of edges to add/remove
        aux_1 = np.random.randint(0,sample+1)
        aux_2 = sample - aux_1
        add_node, delete_node = max(aux_1, aux_2), min(aux_1, aux_2)

        # Remove existing followEvent on the edge_list, and/or create a copy
        el = edge_list.loc[edge_list['type'] != 'FollowEvent'].reset_index(drop=True).copy()
        # Create random new edges and add them to the edge list.
        d = {'source':np.random.choice(self.users, add_node), 'target':np.random.choice(self.repos, add_node), 'type':np.random.choice(self.event_types, add_node)}
        el = pd.concat([el, pd.DataFrame(d)], ignore_index=True, axis=0)

        # Delete edges if delete_node > 0:
        if delete_node > 0:
            aux_el = None
            # Check that removing edges dont remove users or repos.
            timeout = time.time() + 60*2 # 2 minutes from now, max.
            while aux_el is None or not len(aux_el['source'].unique()) == len(self.users) or not len(aux_el['target'].unique()) == len(self.repos):
                if time.time() > timeout or delete_node == 0:
                    #logging.warning(f'Delete nodes time exceeded, adding: {add_node}, deleting: {delete_node}')
                    aux_el = el
                    break
                drop_idxs = np.random.choice(el.index, delete_node, replace=False)
                aux_el = el.drop(drop_idxs).reset_index(drop=True)
                delete_node -= 1 # shrink delete_node to find combination easily.
            
            el = aux_el
        
        et = time.time()
        logging.debug(f'"def":"mutate", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return el

    def map_combinations(self, edge_list):
        st = time.time()
        # Remove followEvent (The assumption is that all users have them) Group all events of a user. Then, map the corresponding value for each combination.
        edge_list = edge_list.loc[edge_list['type'] != 'FollowEvent'].reset_index(drop=True)
        map_values = edge_list[['source','type']].groupby('source').apply(lambda x: self.combinations.get(tuple(sorted(x['type'].unique()))))
        
        et = time.time()
        logging.debug(f'"def":"map_combinations", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return map_values

    def graph_metrics(self, edge_list):
        
        # Evaluate Degree and Pagerank centralities for each node in a Graph
        vertices = self.complete_edgelist(edge_list)
        st = time.time()
        G = gt.Graph(directed=True)
        vertices = G.add_edge_list(vertices[['source', 'target']].to_numpy(), hashed=True)
        ranks = gt.pagerank(G)
        d = [{'vertices':name, 'pagerank':ranks[vertex], 'degree':vertex.out_degree()+vertex.in_degree()} for vertex, name in zip(G.vertices(), vertices)]
        result = pd.DataFrame(d).set_index('vertices')
 
        # filter users, concatenate with mapped values
        result = result[result.index.str.startswith('u: ')]
        et = time.time()
        mapped_values = self.map_combinations(edge_list)
        t1 = et - st
        st = time.time()
        result = pd.concat([result, mapped_values], axis=1, ignore_index=False).rename(columns={0:'Values'})
        
        # Scale values
        result = result.apply(lambda x:(x.astype(float) - min(x))/(max(x)-min(x)), axis = 0)

        et = time.time()
        logging.debug(f'"def":"graph_metrics", "elapsed_time":"{et-st+t1}", "iter":"{self.iter_n}"')
        return result

    def objective(self, candidate):  
        candidate = self.graph_metrics(candidate)
        # Evaluate metrics in terms of star-discrepancy
        st = time.time()
        evaluation = qmc.discrepancy(candidate, method='L2-star',workers=-1)
        et = time.time()
        logging.debug(f'"def":"objective", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return evaluation

    def es_plus(self, n_iter, mu, lam, A = 2, b = 0.5, disable_progress_bar=False):
        st = time.time()
        logging.info(f'ES({mu} + {lam}), start_time: {time.ctime()}')
        
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
        for epoch in (pbar := tqdm(range(n_iter), disable=disable_progress_bar)):
            # change iteration number (iter_n) for logging purposes.
            self.iter_n = epoch
            # sample from binomial distribution > 0
            sample = np.random.binomial(n, prob)
            if sample < 1: sample = 1 # set lower bound
            pbar.set_description(f'best score: {best_eval:.5f}, step_size: {sample}, progress')           
            # evaluate the fitness for the population
            scores = self.pool.map(self.objective, population)
            # rank scores in ascending order
            ranks = np.argsort(np.argsort(scores))
            logging.info(f'n_iter: {epoch}, best_score: {scores[ranks.tolist().index(0)]:.5f}, sample_size: {sample}')
            # select the indexes for the top mu ranked solutions, drop the worse results
            selected = [i for i,_ in enumerate(ranks) if ranks[i] < mu]
            # create offspring from parents
            offspring = list()
            for i in selected:
            # check if this parent is the best solution ever seen
                count = 0 # add a counter of successful candidates
                if scores[i] < best_eval:
                    count += 1
                    best, best_eval, niter = population[i], scores[i], epoch
                # keep the parent
                offspring.append(population[i])
                # create offspring for parent
                for _ in range(n_children):
                    child = self.mutate(population[i], sample)
                    offspring.append(child)
            # replace population with children
            population = offspring
            if count > 0: prob = min(prob*A, 1) #increase success prob when successful candidates were encountered
            else: prob = max(prob*b, 0) # decrease prob.
        et = time.time()
        logging.debug(f'"def":"es_plus", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return niter, best, best_eval

    # Without the following two formulas, you get NotImplementedError 
    # see ref: https://stackoverflow.com/questions/25382455/python-notimplementederror-pool-objects-cannot-be-passed-between-processes
    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['pool']
        return self_dict

    def __setstate__(self, state):
        self.__dict__.update(state)
