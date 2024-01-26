import ast
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
try:
    from prometheus_pandas import query
except:
    pass

class SuccessRate():

    def read(self, path):
        with open (path, encoding='utf-8') as f:
            log_file = " ".join(line.strip() for line in f)
            log_file = re.findall(r'\{[^}]*\}', log_file, re.DOTALL)
            log_file = [{"time": re.search(r'"time": "(.*?)",', i, re.DOTALL).group(1),
            "levelname": re.search(r'"levelname": "(.*?)",', i, re.DOTALL).group(1),
            "message": re.search(r'"message": "(.*?)"', i, re.DOTALL).group(1)} for i in log_file]

        return  log_file

    def relevant_data_to_df(self,data):
        # Transform list to pandas df:
        df = pd.DataFrame(data)
        # Filter out WARNING messages:
        df = df[df['levelname'] != 'WARNING'].reset_index(drop=True)
        # Expand remaining levelname messages INFO, CRITICAL
        df = pd.get_dummies(df, columns=['levelname'])
        # Calculate cumulative sum of INFO, CRITICAL events
        df['accum_INFO'] = df['levelname_INFO'].cumsum()
        try:
            df['accum_CRITICAL'] = df['levelname_CRITICAL'].cumsum()
        except KeyError:
            df['accum_CRITICAL'] = 0
            df['levelname_CRITICAL'] = 0
        df['loaded_evens'] = list(range(1, df.shape[0]+1))
        df['success_rate'] = df['accum_INFO'] / df['loaded_evens']
        
        return df
    
    def plot_df(self,df,ax, dataset_name):

        ax.plot(df.index, df['accum_INFO'],label='Successfully loaded events')
        ax.plot(df.index, df['accum_CRITICAL'],label=f'Failed to load events {df.levelname_CRITICAL.sum()}')
        ini_time = df.time[0]
        end_time = df.time[df.shape[0]-1]
        loading_time = round((pd.to_datetime(end_time) - pd.to_datetime(ini_time)).total_seconds()/3600,1)
        ax.set_title(f'{dataset_name} dataset \n start: {ini_time} \n end: {end_time} \n total loading time: {loading_time} hrs.')
        print(ini_time, end_time)
        ax.set_xlabel('Number of Events')
        ax.set_ylabel('Number of Events')
        ax.legend()

        return ax
    
class PrometheusResuts():
    # 3 steps procedure to retrieve data from prometheus db.

    def read(self, logfile_path):
        # 1. Read logfile from Gitlab's loaded data
        with open(logfile_path, encoding='utf-8') as f:
            text_file = " ".join(line.strip() for line in f)

        # Split the string on the curly braces
        text_file = re.findall(r'\{[^}]*\}', text_file)
        text_file = [ast.literal_eval(item) for item in text_file]

        data = pd.DataFrame(text_file).rename(columns={'time':'start'})

        return data
    
    def start_finish_times(self, df):
        # 2.1 Calculate start/finish times from log file 
        df['finish'] = df['start'].shift(-1).fillna(method='ffill')
        msj = df['message'].to_list()
        st = df['start'].to_list()
        fs = df['finish'].to_list()
        ln = df['levelname'].to_list()

        ndf = pd.DataFrame({'start':st[:-2], 'finish':fs[:-2], 'message':msj[1:-1],'levelname':ln[1:-1]})

        return ndf

    def time_delta(self, df):
        # 2.2 Caclulate time delta for each event
        df['idx'] = df['message'].apply(lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else None)
        df = df[df['levelname'] == "INFO"].reset_index(drop=True)
        df = df.set_index('idx')


        df['start'] = pd.to_datetime(df['start']) #, format='%m/%d/%Y %I:%M:%S %p'
        df['finish'] = pd.to_datetime(df['finish']) #, format='%m/%d/%Y %I:%M:%S %p'
        df['delta'] = (df['finish'] - df['start']).dt.total_seconds()

        return df

    def join_df(self, input_path, output_path, times_df):
        # 3. Join event times/types with source/target from oginal input data:
        df = pd.read_csv(input_path)
        merged = times_df.join(df)
        merged.to_csv(output_path,index=False)

    ####### after completing previous steps, we can now query prometheus #######

    def select_query(self, p, metric, init, endt, step, avg):
        # querys to retrieve cpu, latency, memory and rps
        it = pd.Timestamp(init).strftime('%Y-%m-%dT%H:%M:%SZ')
        et = pd.Timestamp(endt).strftime('%Y-%m-%dT%H:%M:%SZ')

        METRICS = {'cpu':'max(max_over_time(gitlab_sli:gitlab_service_saturation:ratio{component="cpu"}[1m]))',
                   'latency':'sum by (instance) (rate(nginx_vts_upstream_request_seconds_total{instance="localhost:8060"}[1m])) \
                    /sum by (instance) (rate(nginx_vts_upstream_requests_total{instance="localhost:8060"}[1m]))',
                   'memory':'clamp_min(clamp_max(1 -((node_memory_MemFree_bytes{instance="localhost:9100"} \
                    + node_memory_Buffers_bytes{instance="localhost:9100"} \
                    + node_memory_Cached_bytes{instance="localhost:9100"}))\
                    /node_memory_MemTotal_bytes{instance="localhost:9100"},1),0)',
                   'rps':'max(avg_over_time(gitlab_sli:code_method_route:workhorse_http_request_count:rate1m[1m]))'}

        if avg:
            return p.query_range(METRICS[metric], it, et, step).mean().iloc[0]
        else:
            return p.query_range(METRICS[metric], it, et, step)
        
        # if metric == 'cpu':
        #     return p.query_range('max(max_over_time(gitlab_sli:gitlab_service_saturation:ratio{component="cpu"}[1m]))',
        #             it, 
        #             et, 
        #             step).mean().iloc[0]
        # if metric == 'latency':
        #     return p.query_range('sum by (instance) (rate(nginx_vts_upstream_request_seconds_total{instance="localhost:8060"}[1m])) \
        #             /sum by (instance) (rate(nginx_vts_upstream_requests_total{instance="localhost:8060"}[1m]))',
        #             it,
        #             et, 
        #             step).mean().iloc[0]
            
        # if metric == 'memory':
        #     return p.query_range('clamp_min(clamp_max(1 -((node_memory_MemFree_bytes{instance="localhost:9100"} \
        #             + node_memory_Buffers_bytes{instance="localhost:9100"} \
        #             + node_memory_Cached_bytes{instance="localhost:9100"}))\
        #             /node_memory_MemTotal_bytes{instance="localhost:9100"},1),0)',
        #             it,
        #             et, 
        #             step).mean().iloc[0]
        
        # if metric == 'rps':
        #     return p.query_range('max(avg_over_time(gitlab_sli:code_method_route:workhorse_http_request_count:rate1m[1m]))',
        #                         it, 
        #                         et, 
        #                         step).mean().iloc[0]

    def query_db(self, input_path, output_path):
        # join query into a unique df and export it as csv
        p = query.Prometheus('http://localhost:9090')
        df = pd.read_csv(input_path)

        df.loc[:,'cpu'] = df.apply(lambda x: self.select_query(p,'cpu', x['start'], x['finish'], x['delta'], True), axis=1)
        df.loc[:,'mem'] = df.apply(lambda x: self.select_query(p,'memory', x['start'], x['finish'], x['delta'], True), axis=1)
        df.loc[:,'lat'] = df.apply(lambda x: self.select_query(p,'latency', x['start'], x['finish'], x['delta'], True), axis=1)

        c = df[['source', 'cpu']].groupby('source').mean()
        m = df[['source', 'mem']].groupby('source').mean()
        l = df[['source', 'lat']].groupby('source').mean()

        ds = c.join(m).join(l)
        ds = ds.reset_index()

        ds.to_csv(output_path, index=False)


    def global_metrics(self, input_path, output_path):

        p = query.Prometheus('http://localhost:9090')
        df = pd.read_csv(input_path)
        init, endt = df.iloc[1,df.columns.get_loc('start')], df.iloc[-1,df.columns.get_loc('finish')]

        for metric in ['cpu', 'latency', 'memory', 'cpu']:
            ds = self.select_query(p=p, metric=metric, init=init, endt=endt, step=60, avg=False)
            ds.to_csv(output_path+metric+'.csv', index=False)

class ExpandDataset():
    
    def read(self, path, ori=False):
        # read dataset

        df = pd.read_csv(path)
        if ori:
            df = df[df['type'] != 'FollowEvent'].reset_index(drop=True)
        total_events = df.value_counts('type')
        sum_of_total_events = sum(total_events)
        try:
            follow_events = total_events.loc['FollowEvent']
        except:
            follow_events = 0
        non_follow_events = sum_of_total_events - follow_events

        return df, sum_of_total_events, follow_events, non_follow_events

    def random(self, original_path, evolved_path, seed=42):
        # Create Random version
        
        ori = self.read(original_path, ori=True)
        evo = self.read(evolved_path)

        delta_non_follow_events = evo[3] - ori[3]
        delta_follow_events = evo[2] - ori[2]  #TODO: should be equal to evolved followevents

        users = list(set([x for x in ori[0]['source'].to_list()+ori[0]['target'].to_list() if x.startswith('u: ')]))
        repos = list(set([x for x in ori[0]['source'].to_list()+ori[0]['target'].to_list() if x.startswith('r: ')]))
        non_followevents = ['PushEvent','PullRequestEvent','WatchEvent','ForkEvent']

        # create n (n=delta_non_follow_events) random non-follow events
        ran_non_follow_events = pd.DataFrame({'source':np.random.choice(users, delta_non_follow_events), 
                                 'target':np.random.choice(repos, delta_non_follow_events), 
                                 'type':np.random.choice(non_followevents, delta_non_follow_events)})
        
        # create all possible FollowEvents and randomly sample n (n=delta_follow_events)
        a = np.ones((len(users),len(users)), dtype=np.int8)
        np.fill_diagonal(a, 0)
        sources, targets = np.nonzero(a)
        ran_follow_events = pd.DataFrame({'source':list(map(users.__getitem__, sources)), 
                                        'target':list(map(users.__getitem__, targets))})
        ran_follow_events = ran_follow_events.sample(delta_follow_events, replace=True, random_state=seed)
        ran_follow_events['type'] = 'FollowEvent'

        ran = pd.concat([ori[0], ran_non_follow_events, ran_follow_events], ignore_index=True) # TODO: ori should exclude followevents

        return ran

    def simple(self, original_path, evolved_path, seed=42):
        # Create Simple version
        
        ori = self.read(original_path, ori=True)
        evo = self.read(evolved_path)

        delta_non_follow_events = evo[3] - ori[3]
        delta_follow_events = evo[2] - ori[2] #TODO: should be equal to evolved followevents

        # sample n (n=delta_non_follow_events) from original (ori) events:
        ori_non_follow_events = ori[0].sample(n=delta_non_follow_events, replace=True, random_state=seed)
        # duplicate followevents
        ori_follow_events = self.read(original_path)
        ori_follow_events = ori_follow_events[0][ori_follow_events[0]['type'] == 'FollowEvent']
        ori_follow_events = ori_follow_events.sample(n=delta_follow_events, replace=True, random_state=seed)
        # concat data
        sim = pd.concat([ori[0], ori_non_follow_events, ori_follow_events], ignore_index=True) # TODO: ori should exclude followevents

        return sim
