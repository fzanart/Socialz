# Python-Gitlab API wrapper for Socialz research project by Francisco Zanartu

import numpy as np
import time
from gitlab import Gitlab
import re
import random
from gitlab.exceptions import GitlabCreateError, GitlabGetError

#TODO: Add additional step to pull request, commits -> Creating a commit does not allow to push same pull request.
# creating a new branch is still needed.
#TODO: Add create commit method DONE!
#TODO: Add method to read the corpus DONE!
#TODO: 

with open('Data/Corpus/corpus.txt') as f:
    corpus = f.read().splitlines()


class gitlab_flow():
    def __init__(self, host, token, corpus=corpus, max_attemps=100):

        self.host = host
        self.token = token
        self.corpus = corpus
        self.max_attemps = max_attemps
        self.gl = Gitlab(url = self.host, private_token = self.token)

    def replace_bot_substring(self, strg):
        # Replace forbidden characters on Gitlab
        output = re.sub(r"\[bot]", "-bot", strg, re.IGNORECASE) #replace [bot] for -bot
        output = re.sub(r"^[\W_]+|[\W_]+$","",output, re.IGNORECASE) #remove leading and trailing special characters
        return output

    def create_user(self, user_name):
        #Create a user
        user_data = {'email': user_name+'@mail.com', 
                    'username': user_name, 
                    'name': user_name, 
                    'reset_password':False, 
                    'password':'password',
                    'skip_confirmation':True}
        self.gl.users.create(user_data)

    def create_repo(self,repo_name, repo_owner):
        #Create a gitlab project (Github repo)
        project_data = {'name': repo_name, 
                        'visibility':'public', 
                        'initialize_with_readme':True}
    
        self.gl.projects.create(project_data, sudo=repo_owner)
        
        return self.gl.projects.get(f'{repo_owner}/{repo_name}')

    def create_fork(self, project, user_name):
        #List all forks from project, get user_name and forked project id:
        fork_list =  [(fork.attributes.get('owner').get('username'), fork.attributes.get('id'))
                    for fork in project.forks.list(get_all=True)]
    
        fork_list_users = [item[0] for item in fork_list]
        
        # If user_name not in fork_list, fork it:
        if user_name not in fork_list_users:
            try:
                forked_project = project.forks.create({}, sudo=user_name)
                
            except GitlabCreateError:
                
                try:
                    forked_project = project.forks.create({'name':project.name+'_'+user_name, 'path':user_name}, sudo=user_name)
                except:
                    attempt = 0
                    while attempt < 5:
                        attempt += 1
                        try:
                            forked_project = project.forks.create({'name':project.name+'_'+user_name+'_'+str(attempt), 'path':user_name+'_'+str(attempt)}, sudo=user_name)
                        except:
                            continue
                        break        
            
            return self.gl.projects.get(id=forked_project.id)
        else:
        # Get index of forked project if exist:
            indices = [i for i, tupl in enumerate(fork_list) if tupl[0] == user_name]
            return self.gl.projects.get(id=fork_list[indices[0]][1])

    def create_commit(self, project, branch, user_name, action='update'):
        # actions: create, delete, move, update, chmod
        commit_data = {'branch': branch,
                    'commit_message': f'{self.title}\n{self.message}',
                    'actions': [{
                    'action': action,
                    'file_path': 'README.md',
                    'content': self.body}]}
        project.commits.create(commit_data, sudo=user_name)

    def create_watch(self, project, user):
        # Star a project (repo), otherwise, unstar.
        try:
            project.star(sudo=user)
        except GitlabCreateError:
            project.unstar(sudo=user)

    def create_follow(self, user, user_to_follow):
        # Create a follow relaton between one user an another.
        follower_user = self.gl.users.list(username=user_to_follow)[0]
        follower_user.follow(sudo=user)

    def create_pull_request(self, project, head_branch, base_branch, tarject_project_id, user_name, repo_owner, repo_name):
        try:
            # Try creating pull request as it is.
            project.mergerequests.create({'source_branch':head_branch,
                                      'target_branch':base_branch,
                                      'title':'Untitled',
                                      'body':'Empty',
                                      'target_project_id':tarject_project_id}, sudo=user_name)
        except GitlabCreateError:
            # Except creating pull request with max_attemps different branch names.
            attempt = 0
            while attempt < self.max_attemps:
                branch_rename = f'{head_branch}_{len(project.branches.list(get_all=True))+attempt}'

                try:
                    project.branches.create({'branch': branch_rename,'ref': 'main'}, sudo=user_name)
                    project.mergerequests.create({'source_branch':branch_rename,
                                                'target_branch':base_branch,
                                                'title':'Untitled',
                                                'body':'Empty',
                                                'target_project_id':tarject_project_id}, sudo=user_name)
                    break
                except GitlabCreateError:
                    attempt +=1


    def pull_request(self, repo_name, repo_owner, user_name):

        user_name = self.replace_bot_substring(user_name)
        repo_owner = self.replace_bot_substring(repo_owner)
        repo_name = self.replace_bot_substring(repo_name)
        head_branch, base_branch = 'head_branch', 'base_branch'

        # 1. Create user if it does no exist:
        if user_name not in [x.username for x in self.gl.users.list(search=user_name)]:
            self.create_user(user_name)

        # 2. Create repo owner user if it does no exist:
        if repo_owner not in [x.username for x in self.gl.users.list(search=repo_owner)]:
            self.create_user(repo_owner)

        # 3. Create repo if it does not exist:
        try:
            time.sleep(1)
            project = self.gl.projects.get(f'{repo_owner}/{repo_name}')
        except GitlabGetError:
            project = self.create_repo(repo_name, repo_owner)

        tarject_project_id = project.id

        # 4. Create source (base) branch if it does not exist:
        try:
            time.sleep(1)
            project.branches.get(base_branch)
        except GitlabGetError:
            project.branches.create({'branch': base_branch,'ref': 'main'}, sudo=repo_owner)

        # 5. Fork project if user_name != repo_owner
        if user_name != repo_owner:
            forked_project = self.create_fork(project, user_name)

            # 6. Create target (head) branch if it does not exist:
            try:
                time.sleep(1)
                forked_project.branches.get(head_branch)
            except GitlabGetError:
                forked_project.branches.create({'branch': head_branch,'ref': 'main'}, sudo=user_name)

            # 7. Create merge request (pull request):
            self.create_pull_request(project, head_branch, base_branch, tarject_project_id, user_name, repo_owner, repo_name)

        # if user_name == repo_owner, there is no need to fork
        else:
            # 6. Create target (head) branch if it does not exist:
            try:
                time.sleep(1)
                project.branches.get(head_branch)
            except GitlabGetError:
                project.branches.create({'branch': head_branch,'ref': 'main'}, sudo=user_name)

            # 7. Create merge request (pull request):
            self.create_pull_request(project, head_branch, base_branch, tarject_project_id, user_name, repo_owner, repo_name)


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