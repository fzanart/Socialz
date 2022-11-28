import numpy as np
import time
from gitlab import Gitlab
import re
import random
from gitlab.exceptions import GitlabCreateError, GitlabGetError       

class gitlab_flow():
    def __init__(self, host, token, corpus_path='Data/Corpus/corpus.txt', max_attemps=5):

        self.host = host
        self.token = token
        self.corpus_path = self.get_corpus(corpus_path)
        self.max_attemps = max_attemps
        self.gl = Gitlab(url = self.host, private_token = self.token)

    def get_corpus(self, corpus_path):
        # Read corpus to create random text titles, messages, body.
        with open(corpus_path) as f:
            corpus = f.read().splitlines()
            return corpus

    def replace_bot_substring(self, strg):
        # Replace forbidden characters on Gitlab
        output = re.sub(r"\[bot]", "-bot", strg, re.IGNORECASE) #replace [bot] for -bot
        output = re.sub(r"^[\W_]+|[\W_]+$","",output, re.IGNORECASE) #remove leading and trailing special characters
        return output

    def create_user(self, user_name):
        #Create a user
        user_data = {'email': user_name+'@mail.com', 'username': user_name, 'name': user_name, 'reset_password':False, 'password':'password','skip_confirmation':True}
        return self.gl.users.create(user_data)

    def create_repo(self,repo_name, repo_owner):
        #Create a gitlab project (Github repo)
        project_data = {'name': repo_name, 'visibility':'public','initialize_with_readme':True}
        self.gl.projects.create(project_data, sudo=repo_owner)
        return self.gl.projects.get(f'{repo_owner}/{repo_name}')            

    def validate(self, source, target):
        # Validate user, repo owner (user) and repo to exist.
        user_name = self.replace_bot_substring(source)
        repo_owner, repo_name = target.split('/')
        repo_owner = self.replace_bot_substring(repo_owner)
        repo_name = self.replace_bot_substring(repo_name)
        
        # 1. Create user if it does no exist:
        user_list = [x.username for x in self.gl.users.list(search=user_name)]
        if user_name not in user_list:
            user_name = self.create_user(user_name)
        else:
            user_name = self.gl.users.list(username=user_name)[0]

        # 2. Create repo owner user if it does no exist:
        repo_list = [x.username for x in self.gl.users.list(search=repo_owner)]
        if repo_owner not in repo_list:
            repo_owner = self.create_user(repo_owner)
        else:
            repo_owner = self.gl.users.list(username=repo_owner)[0]

        # 3. Create repo if it does not exist:
        try:
            project = self.gl.projects.get(f'{repo_owner.username}/{repo_name.username}')
        except GitlabGetError:
            project = self.create_repo(repo_name.username, repo_owner.username)

        # 4. if user can not commit/merge request, invite:
        if user_name.username not in project.users.list(search=user_name.username):
            project.invitations.create({"user_id": user_name.id,"access_level": 40,}, sudo=repo_owner.username) #TODO: SUDO? repo_owner?

        return user_name, repo_owner, project

    def create_commit(self, source, target, branch='main', action='update'):
        # Create PushEvent, actions: create, delete, move, update, chmod
        user_name, repo_owner, project = self.validate(source, target)   
        commit_data = {'branch': branch,'commit_message': f'{self.title()}\n{self.message()}','actions': [{'action': action,'file_path': 'README.md','content': self.body()}]}
        project.commits.create(commit_data, sudo=user_name.username)


    def create_fork(self, source, target):
        # Create ForkEvent, retry if fork exist or there is a name conflict:
        user_name, repo_owner, project = self.validate(source, target)
        try:
            project.forks.create({}, sudo=user_name.username)
        except GitlabGetError:
            attempt = 0
            while attempt < 5:
                try:
                    project.forks.create({'name':project.name+'_'+user_name.username+'_'+str(attempt), 'path':user_name.username+'_'+str(attempt)}, sudo=user_name.username)
                except:
                    attempt += 1
                    continue
                break

    def create_watch(self, source, target):
        # Star a project (repo), otherwise, unstar.
        user_name, repo_owner, project = self.validate(source, target)
        try:
            project.star(sudo=user_name.username)
        except GitlabCreateError:
            project.unstar(sudo=user_name.username)

    def create_follow(self, source, target):
        # Create a follow relaton between one user to another.
        source = self.replace_bot_substring(source)
        target = self.replace_bot_substring(source)

        if source not in [x.username for x in self.gl.users.list(search=source)]:
            source = self.create_user(source)
        if source not in [x.username for x in self.gl.users.list(search=target)]:
            target = self.create_user(target)

        try:
            target.follow(sudo=source)
        except:
            target.unfollow(sudo=source)

    def create_pull_request(self, source, target):
        # Create pull request by inviting user as project member.
        # (1) Validate source, target, invitation
        user_name, repo_owner, project = self.validate(source, target)
        head_branch, base_branch = 'head_branch', 'main'
        
        # (2) list all opened branches, if branches < 1 (only main exist) create new one.
        branches = project.branches.list(state='opened', get_all=True)
        if len(branches) < 1:
            head_branch = project.branches.create({'branch': 'head_branch','ref': 'main'}, sudo=user_name.username)
            project.mergerequests.create({'source_branch':head_branch,'target_branch':base_branch,'title':self.title(),'body':self.body(),'target_project_id':project.id}, sudo=user_name.username)

        else:
        # (3) if it is there less than one merge request, create one: 
            mr_len = len(project.mergerequests.list(get_all = True))
            if mr_len < 1:
                head_branch = np.random.choice([branch.name for branch in project.branches.list(state='opened', get_all=True)])
                project.mergerequests.create({'source_branch':head_branch,'target_branch':base_branch,'title':self.title(),'body':self.body(),'target_project_id':project.id}, sudo=user_name.username)
            else: # (3.1) else, pick a random merge request
                mr = project.mergerequests.get(project.mergerequests.list(get_all = True)[np.random.choice(mr_len)].iid)
                if mr.state == 'closed': # opened, closed, merged or locked.
                    # (3.2) if closed, reopen.
                    mr.state_event = 'reopen'
                    mr.save(sudo=user_name.username)
                if mr.state == 'opened':
                    # (3.3) If opened, merge or close.
                    if np.random.choice(['merge', 'close']) == 'merge':
                        #should_remove_source_branch: If true, removes the source branch.
                        mr.merge(should_remove_source_branch = True, sudo=user_name.username)
                    else:
                        mr.state_event = 'closed'
                        mr.save(sudo=user_name.username)
                else: #(3.4) if merged, create a new branch/merge request.
                    #create a new branch / merge request.
                    branch_rename = f'{head_branch}_{len(project.branches.list(get_all=True))}'
                    project.mergerequests.create({'source_branch':branch_rename,'target_branch':base_branch,'title':self.title(),'body':self.body(),'target_project_id':project.id}, sudo=user_name.username)

    def title(self):
        # n represents the lenght of the text, how many words.
        n = random.randint(18,42)
        return ' '.join(random.choices(self.corpus, k=n))

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
            if edge_list['type'][i] == 'PushEvent':
                self.create_commit(edge_list['source'][i],edge_list['target'][i])
            if edge_list['type'][i] == 'ForkEvent':
                self.create_fork(edge_list['source'][i],edge_list['target'][i])
            if edge_list['type'][i] == 'WatchEvent':
                self.create_watch(edge_list['source'][i],edge_list['target'][i])
            if edge_list['type'][i] == 'FollowEvent':
                self.create_follow(edge_list['source'][i],edge_list['target'][i])
            else:
                print('event not allowed')
                break
