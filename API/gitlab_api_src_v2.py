import numpy as np
import time
from gitlab import Gitlab
import re
import random
import json
import logging
from gitlab.exceptions import GitlabCreateError, GitlabGetError,GitlabListError, GitlabHttpError       

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
class gitlab_flow():
    def __init__(self, host, token, corpus_path='Data/Corpus/corpus.txt', max_attemps=5, db_waiting_time=0.25):

        self.host = host
        self.token = token
        self.corpus = self.get_corpus(corpus_path)
        self.max_attemps = max_attemps
        self.db_waiting_time = db_waiting_time # db needs some time before creating a project or an invitation for a new user, or a branch for a new project.
        self.gl = Gitlab(url = self.host, private_token = self.token)

    def get_corpus(self, corpus_path):
        # Read corpus to create random text titles, messages, body.
        with open(corpus_path) as f:
            corpus = f.read().splitlines()
            return corpus

    def amend_name(self, name:str):
        # Replace forbidden characters on Gitlab
        validation = re.compile(r'^(?!-|\.git$|\.atom$)[a-zA-Z0-9][a-zA-Z0-9_.-]*[a-zA-Z0-9]$')
        try:
            amended_name = re.match(validation, name).string
            return amended_name
        except:
            try:
                amended_name = re.sub(r'\[bot]','-bot', name, re.IGNORECASE) #replace [bot] for -bot
                amended_name = re.sub(r"^[\W_]+|[\W_]+$","",amended_name, re.IGNORECASE) #remove leading and trailing special characters
                amended_name = re.match(validation, amended_name).string
                return amended_name
            except:
                amended_name = name.replace('-','45') # for repo named '-', user 'v--' replace hyphen with its ASCII code => 45.
                return amended_name

    def create_user(self, user_name):
        #Create a user
        user_data = json.loads(json.dumps({'email': user_name+'@mail.com', 'username': user_name, 'name': user_name, 'reset_password':False, 'password':'password','skip_confirmation':True}))
        try:
            return self.gl.users.create(user_data)
        except GitlabCreateError:
            timeout = 0
            while user_name not in [x.username for x in self.gl.users.list(search=user_name, get_all=True)] and timeout < 8:
                time.sleep(self.db_waiting_time)
                logging.debug(f'waiting user creation')
                timeout +=1
            return self.gl.users.list(username=user_name, get_all=True)[0]

    def create_repo(self,repo_name, repo_owner):
        #Create a gitlab project (Github repo)
        project_data = json.loads(json.dumps({'name': repo_name, 'visibility':'public','initialize_with_readme':True}))
        self.gl.projects.create(project_data, sudo=repo_owner.id)
        return self.gl.projects.get(f'{repo_owner.username}/{repo_name}')

    def validate(self, source, target, invite=True, repo=True):
        # Validate user, repo owner (user) and repo to exist.
        user_name = self.amend_name(source)
        if repo:
            repo_owner, repo_name = target.split('/')
            repo_owner = self.amend_name(repo_owner)
            repo_name = self.amend_name(repo_name)
        else:
            repo_owner = self.amend_name(target)
        
        # 1. Create user if it does no exist:
        if user_name not in [x.username for x in self.gl.users.list(search=user_name, get_all=True)]:
            user_name = self.create_user(user_name)
        else:
            user_name = self.gl.users.list(username=user_name, get_all=True)[0]

        # 2. Create repo owner user if it does no exist:
        if repo_owner not in [x.username for x in self.gl.users.list(search=repo_owner, get_all=True)]:
            repo_owner = self.create_user(repo_owner)
            try:
                while repo_owner not in [x.username for x in self.gl.users.list(search=repo_owner, get_all=True)]:
                    time.sleep(self.db_waiting_time) # db needs some time before creating a project for a new user.
                    logging.debug(f'waiting user creation')
            except (GitlabHttpError, GitlabListError) as e:
                time.sleep(self.db_waiting_time*4)
                logging.debug(f'user creation is taking too long...')

        else:
            repo_owner = self.gl.users.list(username=repo_owner, get_all=True)[0]

        # 3. Create repo if it does not exist:
        if repo:
            try:
                project = self.gl.projects.get(f'{repo_owner.username}/{repo_name}')
            except GitlabGetError:
                project = self.create_repo(repo_name, repo_owner)
        
        # 4. if user can not commit/merge request, invite:
        if invite and user_name.username != repo_owner.username:
            if user_name.id not in [x.id for x in project.users.list(search=user_name.username, get_all=True)]:
                invitation = project.invitations.create(json.loads(json.dumps({"user_id": user_name.id,"access_level": 40,})), sudo=repo_owner.id)
                try:
                    while user_name.id not in [x.id for x in project.users.list(search=user_name.username)]:
                        time.sleep(self.db_waiting_time) # db needs some time before creating a project for a new user.
                        logging.debug(f'waiting invitation')
                except (GitlabHttpError, GitlabListError) as e:
                    time.sleep(self.db_waiting_time*4)
                    logging.debug(f'user invitation is taking too long...')
        if repo:
            return user_name, repo_owner, project
        else:
            return user_name, repo_owner

    def create_commit(self, source, target, action='update'):
        # Create PushEvent, actions: create, delete, move, update, chmod
        user_name, repo_owner, project = self.validate(source, target)   
        branch = np.random.choice([branch.name for branch in project.branches.list(get_all=True)])
        commit_data = json.loads(json.dumps({'branch': branch,'commit_message': f'{self.title()}\n{self.message()}','actions': [{'action': action,'file_path': 'README.md','content': self.body()}]}))
        try: # Try commiting to a random branch.
            return project.commits.create(commit_data, sudo=user_name.id)
        except GitlabCreateError: # If we get an error, try commiting to another branch.
            timeout = 0
            while timeout < 8:
                try:
                    another_branch = np.random.choice([b.name for b in project.branches.list(get_all=True) if b.name != branch])
                    commit_data = json.loads(json.dumps({'branch': another_branch,'commit_message': f'{self.title()}\n{self.message()}','actions': [{'action': action,'file_path': 'README.md','content': self.body()}]}))
                    return project.commits.create(commit_data, sudo=user_name.id)
                except GitlabCreateError:
                    time.sleep(self.db_waiting_time)
                    timeout += 1
                    continue
            if timeout >= 8: # If nothing worked, make a last try comiting to main branch.
                commit_data = json.loads(json.dumps({'branch': 'main','commit_message': f'{self.title()}\n{self.message()}','actions': [{'action': action,'file_path': 'README.md','content': self.body()}]}))
                return project.commits.create(commit_data, sudo=user_name.id)
            
    def create_fork(self, source, target):
        # Create ForkEvent, retry if fork exist or there is a name conflict:
        user_name, repo_owner, project = self.validate(source, target)
        try:
            project.forks.create({}, sudo=user_name.id)
        except GitlabCreateError:
            attempt = self.max_attemps
            while attempt < 5:
                try:
                    project.forks.create(json.loads(json.dumps({'name':project.name+'_'+user_name.username+'_'+str(attempt), 'path':user_name.username+'_'+str(attempt)})), sudo=user_name.id)
                except:
                    attempt += 1
                    continue
                break

    def create_watch(self, source, target):
        # Star a project (repo), otherwise, unstar.
        user_name, repo_owner, project = self.validate(source, target, invite=False)
        try:
            project.star(sudo=user_name.id)
        except GitlabCreateError:
            project.unstar(sudo=user_name.id)

    def create_follow(self, source, target):
        # Create a follow relaton between one user to another.
        source, target = self.validate(source, target, invite=False, repo=False)
        try:
            return target.follow(sudo=source.id)
        except:
            return target.unfollow(sudo=source.id)

    def create_pull_request(self, source, target):
        # Create pull request by inviting user as project member.
        # (1) Validate source, target, invitation
        user_name, repo_owner, project = self.validate(source, target)
        head_branch, base_branch = 'head_branch', 'main'
        
        # (2) list all branches, if branches <= 1 (only main exist) create new one.
        branches = project.branches.list(get_all=True)
        if len(branches) <= 1:
            head_branch = project.branches.create(json.loads(json.dumps({'branch': 'head_branch','ref': 'main'})), sudo=user_name.id)
            try:
                while 'head_branch' not in [branch.name for branch in project.branches.list(get_all=True)]:
                    time.sleep(self.db_waiting_time) # db needs some time before creating a project for a new user.
                    logging.debug(f'waiting branch creation')
            except (GitlabHttpError, GitlabListError) as e:
                time.sleep(self.db_waiting_time*4)
                logging.debug(f'branch creation is taking too long...')
                project.mergerequests.create(json.loads(json.dumps({'source_branch':head_branch.name,'target_branch':base_branch,'title':self.title(),'body':self.body(),'target_project_id':project.id})), sudo=user_name.id)
        else:
        # (3) if it is there less than one merge request, create one: 
            mr_len = len(project.mergerequests.list(get_all = True))
            if mr_len < 1:
                head_branch = np.random.choice([branch.name for branch in project.branches.list(get_all=True) if branch.name != 'main'])
                project.mergerequests.create(json.loads(json.dumps({'source_branch':head_branch,'target_branch':base_branch,'title':self.title(),'body':self.body(),'target_project_id':project.id})), sudo=user_name.id)
            else: # (3.1) else, pick a random merge request
                mr = project.mergerequests.get(project.mergerequests.list(get_all = True)[np.random.choice(mr_len)].iid)
                if mr.state == 'closed': # opened, closed, merged or locked.
                    # (3.2) if closed, reopen.
                    mr.state_event = 'reopen'
                    mr.save(sudo=user_name.id)
                if mr.state == 'opened':
                    # (3.3) If opened, merge or close.
                    if mr.merge_status == 'cannot_be_merged' or mr.merge_status == 'checking':
                        mr.state_event = 'close'
                        mr.save(sudo=user_name.id)
                    else:
                        #should_remove_source_branch: If true, removes the source branch.
                        sb, deleting, timeout = mr.source_branch, True, 0
                        mr.merge(should_remove_source_branch = True, sudo=user_name.id)
                        while deleting and timeout < 8:
                            try:
                                project.branches.get(sb)
                                logging.debug(f'waiting mr source branch deletion')
                                time.sleep(self.db_waiting_time)
                                timeout += 1
                            except GitlabGetError:
                                deleting = False

                else: #(3.4) if merged, create a new branch/merge request.
                    #create a new branch / merge request.
                    branch_rename = f'{head_branch}_{len(project.branches.list(get_all=True))}'
                    try:
                        branch_rename = project.branches.create(json.loads(json.dumps({'branch': branch_rename,'ref': 'main'})), sudo=user_name.id)
                        try:
                            while branch_rename.name not in [branch.name for branch in project.branches.list(get_all=True)]:
                                time.sleep(self.db_waiting_time)
                                logging.debug(f'waiting branch re_name creation')
                        except (GitlabHttpError, GitlabListError) as e:
                            time.sleep(self.db_waiting_time*4)
                            logging.debug(f'branch re_name creation is taking too long...')
                        project.mergerequests.create(json.loads(json.dumps({'source_branch':branch_rename.name,'target_branch':base_branch,'title':self.title(),'body':self.body(),'target_project_id':project.id})), sudo=user_name.id)
                    except GitlabCreateError:
                        project.mergerequests.create(json.loads(json.dumps({'source_branch':branch_rename,'target_branch':base_branch,'title':self.title(),'body':self.body(),'target_project_id':project.id})), sudo=user_name.id)


    def title(self):
        # n represents the lenght of the text, how many words.
        # 'title':'is too long (maximum is 255 characters)'
        n = random.randint(18,42)
        return ' '.join(random.choices(self.corpus, k=n))[:255]

    def body(self):
        # n represents the lenght of the text, how many words.
        n = random.randint(42,437)

        # Assign a high prob of more newlines if the text is long
        # or low prob of newlines if the text is short.
        prob = [37, 25, 12, 7, 7, 4, 3, 3, 2]
        
        if n > 337:
            newlines = random.choices(list(range(0,9)), list(reversed(prob)), k=1)[0]
        if n < 140:
            newlines = random.choices(list(range(0,9)), prob, k=1)[0]
        else:
            newlines = random.choices(list(range(0,9)), k=1)[0]

        # create the text
        body = random.choices(self.corpus, k=n)
        # Divide the body in n (newlines) chunks
        body = np.array_split(np.array(body), newlines+1)
        body = [sentence.tolist() for sentence in body]

        # Add newlines
        [sentence.append('\n') for sentence in body]

        # # Join the words
        body = ' '.join([item for sentence in body for item in sentence])
        return body

    def message(self):
        # n represents the lenght of the text, how many words.
        n = random.randint(19,100)
        
        # create the text
        message = random.choices(self.corpus, k=n)
        
        # split the text in half.
        message = np.array_split(np.array(message), 2)
        message = [sentence.tolist() for sentence in message]
        
        # inset the newlines
        [sentence.append('\n') for sentence in message]
        
        # join the words.
        message = ' '.join([item for sentence in message for item in sentence])
        return message

    def flow(self, edge_list):

        for i in edge_list.index:
            if edge_list['type'][i] == 'PullRequestEvent':
                self.create_pull_request(edge_list['source'][i],edge_list['target'][i])
                logging.info(f'{i} PullRequestEvent created')
            if edge_list['type'][i] == 'PushEvent':
                self.create_commit(edge_list['source'][i],edge_list['target'][i])
                logging.info(f'{i} PushEvent created')
            if edge_list['type'][i] == 'ForkEvent':
                self.create_fork(edge_list['source'][i],edge_list['target'][i])
                logging.info(f'{i} ForkEvent created')
            if edge_list['type'][i] == 'WatchEvent':
                self.create_watch(edge_list['source'][i],edge_list['target'][i])
                logging.info(f'{i} WatchEvent created')
            if edge_list['type'][i] == 'FollowEvent':
                self.create_follow(edge_list['source'][i],edge_list['target'][i])
                logging.info(f'{i} FollowEvent created')
            elif edge_list['type'][i] not in ['PullRequestEvent', 'PushEvent', 'ForkEvent','WatchEvent', 'FollowEvent']:
                logging.critical('Event not allowed')
                break
