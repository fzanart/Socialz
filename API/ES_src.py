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
import warnings

logging.basicConfig(filename='evolution_run_logfile.log',
                    filemode='w', #open for exclusive creation, failing if the file already exists.
                    datefmt='%H:%M:%S,uuu',#'%d-%b-%y %H:%M:%S',
                    level=logging.INFO,
                    format='{%(message)s},')
class evolutionary_strategy():

    def __init__(self, edge_list, cpus=4):
        self.iter_n = 0
        self.edge_list = self.validate_edge_list(edge_list)
        self.users = edge_list['source'].unique().tolist()
        self.repos = edge_list['target'].unique().tolist()
        self.cpus = cpus
        self.pool = Pool(self.cpus)
        self.event_types = edge_list['type'].unique().tolist()
        self.combinations = self.get_combinations()
        self.total_nodes = len(self.users + self.repos)
        self.prob_per_event = {event: 0.5 / (len(self.event_types) - 1) for event in self.event_types}

    def validate_edge_list(self, edge_list):

        ALLOWED_EVENT_TYPES = ['PushEvent', 'ForkEvent', 'WatchEvent', 'PullRequestEvent']
        EXPECTED_COLUMNS = ['source', 'target', 'type']

        # Check if edge_list has exactly 3 columns named 'source', 'target', 'type'
        if len(edge_list.columns) != 3 and not all(col in edge_list.columns for col in EXPECTED_COLUMNS):
            raise ValueError("The edge_list must contain exactly 3 columns: ['source', 'target', 'type']")
        
        # Filter rows with types other than allowed types
        invalid_types = edge_list[~edge_list['type'].isin(ALLOWED_EVENT_TYPES)]
        if not invalid_types.empty:
            filtered_types = invalid_types['type'].unique().tolist()
            warnings.warn(f"Filtered out invalid event types: {str(filtered_types)}")
            return edge_list[edge_list['type'].isin(ALLOWED_EVENT_TYPES)].copy()
        else:
            return edge_list

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

    def user_user_similarity(self, repo_user, user_repo):
        st = time.time()
        # Evaluate user-user similarity:
        
        ## Get repo - user similarity (upper-right square):
        repo_user = repo_user/np.linalg.norm(repo_user,axis=0,keepdims=True)
        repo_user[np.isnan(repo_user)] = 0
        repo_user = np.dot(repo_user.transpose(),repo_user)

        ## Get user - repo similarity (lower-left square):
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
        weights = adj_matrix.to_numpy()[sources, targets]
        edge_list = pd.DataFrame({'source':list(map(self.users.__getitem__, sources)), 
                                  'target':list(map(self.users.__getitem__, targets)),
                                  'weight': weights})
        edge_list['type'] = 'FollowEvent'
        et = time.time()
        logging.debug(f'"def":"adjmatrix_to_edgelist", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return edge_list
    
    def edgelist_to_adjmatrix(self, edge_list):
        st = time.time()
        user_repo = edge_list.groupby(['source', 'target'])['target'].count().unstack(fill_value=0)
        repo_user = user_repo.T
        idx = user_repo.columns.union(user_repo.index)
        adj_matrix = user_repo.reindex(index = idx, columns=idx, fill_value=0.0)
        adj_matrix.update(repo_user)
        et = time.time()
        adj_matrix = pd.DataFrame(columns=self.users, index=self.users, data=self.user_user_similarity(repo_user=repo_user, user_repo=user_repo))
        logging.debug(f'"def":"edgelist_to_adjmatrix", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return adj_matrix

    def complete_edgelist(self, edge_list):
        st = time.time()
        # Add user-user FollowEvents based on cosine similarity
        # Remove followEvent if exists on the edge_list
        edge_list = edge_list.loc[edge_list['type'] != 'FollowEvent'].reset_index(drop=True)
        et = time.time()
        # Build the user_user adjacency matrix
        user_user_adj_matrix = self.edgelist_to_adjmatrix(edge_list)
        # Create edge list from user-user similarity:
        user_user_edge_list = self.adjmatrix_to_edgelist(user_user_adj_matrix)
        t1 = et - st
        st = time.time()
        edge_list['weight'] = 2 # add a wight of 2 to each non follow event.
        # Append user_user edge list to edge_list:
        edge_list = pd.concat([edge_list, user_user_edge_list], ignore_index=True, axis=0)
        et = time.time()
        logging.debug(f'"def":"complete_edgelist", "elapsed_time":"{et-st+t1}", "iter":"{self.iter_n}"')
        return edge_list
    
    def add(self, edge_list, add_node):

        # initialise a dict with same prob for all events:
        probs = self.prob_per_event.copy()

        # update prob for least frequent event:
        least_frequent_event = edge_list['type'].value_counts().idxmin()
        probs[least_frequent_event] = 0.5

        # generates a new set of random edges and appends them to the existing edge list.
        d = {'source':np.random.choice(a=self.users, size=add_node, replace=True), 'target':np.random.choice(a=self.repos, size=add_node, replace=True), 'type':np.random.choice(a=self.event_types, size=add_node, replace=True, p=[probs[e] for e in self.event_types])}
        el = pd.concat([edge_list, pd.DataFrame(d)], ignore_index=True, axis=0)
        return el
    
    def delete(self, edge_list, del_nodes):
        # Select from how many nodes I will be deleting edges:
        nodes_to_delete = list(np.random.choice(a=self.users, size=del_nodes, replace=False))
        print(nodes_to_delete)

        # Select all posible edges to be deleted
        mask = edge_list['source'].isin(nodes_to_delete)
        source_nodes_to_delete = edge_list[mask]

        # Exclude nodes without duplicated edges. (avoid deleting nodes)
        edges_to_keep = source_nodes_to_delete.drop_duplicates(subset=['source'], keep=False).index 
        source_nodes_to_delete = source_nodes_to_delete.drop(edges_to_keep)

        if not source_nodes_to_delete.empty:
            # From nodes with more than one edge, pick a random one to be deleted.
            source_nodes_to_delete = source_nodes_to_delete.groupby('source',group_keys=True).apply(lambda x: x.sample(n=1)).index.get_level_values(1)
            el = edge_list.drop(source_nodes_to_delete)
            
        else:
            # Dont delete
            el = edge_list.drop(source_nodes_to_delete.index)

        return el.reset_index(drop=True)

    def mutate(self, edge_list, sample):

        el = edge_list.loc[edge_list['type'] != 'FollowEvent'].reset_index(drop=True).copy()
        choice = np.random.choice(['add', 'delete'], 1)
        choice = ['add']

        if choice[0] == 'add': 
            return self.add(el, sample)
        else: 
            return self.delete(el, sample)

    def map_combinations(self, edge_list):
        st = time.time()
        # Remove followEvent (The assumption is that all users have them) Group all events of a user. Then, map the corresponding value for each combination.
        edge_list = edge_list.loc[edge_list['type'] != 'FollowEvent'].reset_index(drop=True)
        map_values = edge_list[['source','type']].groupby('source').apply(lambda x: self.combinations.get(tuple(sorted(x['type'].unique()))))
        
        et = time.time()
        logging.debug(f'"def":"map_combinations", "elapsed_time":"{et-st}", "iter":"{self.iter_n}"')
        return map_values
    
    # def rnd_choice_pivots(self, percentage):
    #     # randomly chosen vertices, unbiased estimator, for betweenness centrality computation
    #     size = len(self.users + self.repos)
    #     pivots = np.random.choice(a=np.array(range(0,size+1)), size=int(size*percentage), replace=False)
    #     return pivots

    def graph_metrics(self, edge_list, weight=True, scale=True):
        # Evaluate Degree and betweenness centralities for each node in the Graph
        el = self.complete_edgelist(edge_list)
        st = time.time()
        g = gt.Graph(directed=True)
        vertices = g.add_edge_list(el[['source', 'target']].to_numpy(), hashed=True)
        if weight:
            weights = g.new_edge_property('double')
            g.edge_properties['weight'] = weights
            weights.a = el['weight'].to_numpy()
            r = gt.pagerank(g, weight=weights)
        else:
            r = gt.pagerank(g)

        d = [{'vertices':name, 'pagerank':r[vertex], 'degree':vertex.out_degree()+vertex.in_degree()} for vertex, name in zip(g.vertices(), vertices)]
        result = pd.DataFrame(d).set_index('vertices')
 
        # filter users, concatenate with mapped values
        result = result[result.index.str.startswith('u: ')]
        et = time.time()
        mapped_values = self.map_combinations(edge_list)
        t1 = et - st
        st = time.time()
        result = pd.concat([result, mapped_values], axis=1, ignore_index=False).rename(columns={0:'Values'})
        
        # Scale values
        if scale:
            result = result.apply(lambda x:(x.astype(float) - min(x))/(max(x)-min(x)), axis = 0).fillna(0)

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
        n = self.total_nodes
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
            sample = max(np.random.binomial(n, prob), 1)
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
            if count > 0: prob = min(prob*A, 0.5) #increase success prob when successful candidates were encountered
            else: prob = max(prob*b, 1/n**2) # decrease prob.
            pbar.set_description(f'best score: {best_eval:.5f}, step_size: {sample}, progress')           
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