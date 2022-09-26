from os import path
import gitlab
from gitlab.exceptions import GitlabCreateError
import re
import json
import pandas as pd
import time
import logging

log_file_path = path.join(path.dirname(path.abspath(__file__)), 'logging.ini')
logging.config.fileConfig(log_file_path)
logger = logging.getLogger('jsonLogger')

def replace_bot_substring(string):
    #replace [bot] for -bot
    result = re.sub(r"\[bot]", "-bot", string, re.IGNORECASE)
    #remove leading and trailing special characters
    result = re.sub(r"^[\W_]+|[\W_]+$","",result, re.IGNORECASE)
    
    return result

def create_user(gl, user_name):
    user_data = {'email': user_name+'@mail.com', 
                 'username': user_name, 
                 'name': user_name, 
                 'reset_password':False, 
                 'password':'password',
                 'skip_confirmation':True}
    gl.users.create(user_data)

def create_repo(gl, repo_name, repo_owner, project_name_with_namespace):
    project_data = {'name': repo_name, 
                    'visibility':'public', 
                    'initialize_with_readme':True}
    
    gl.projects.create(project_data, sudo=repo_owner)
        
    return gl.projects.get(project_name_with_namespace)

def create_fork(gl, project, user_name):
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
        
        return gl.projects.get(id=forked_project.id)
    else:
        # Get index of forked project if exist:
        indices = [i for i, tupl in enumerate(fork_list) if tupl[0] == user_name]
        return gl.projects.get(id=fork_list[indices[0]][1])
    
def create_pull_request(i, project, head_branch, base_branch, tarject_project_id, user_name,repo_owner, repo_name):
    try:
        project.mergerequests.create({'source_branch':head_branch,
                                      'target_branch':base_branch,
                                      'title':'Untitled',
                                      'body':'Empty',
                                      'target_project_id':tarject_project_id}, sudo=user_name)
    except gitlab.exceptions.GitlabCreateError:
        attempt = 0
        while attempt < 100:
            branch_rename = f'{head_branch}_{len(project.branches.list(get_all=True))+attempt}'
            msg = {"i":i,
                   "attempt":attempt,
                   "user":user_name,
                   "repo":f"{repo_owner}/{repo_name}",
                   "base":base_branch,
                   "head":branch_rename}
            logger.info('Attempting to create pull request',extra=msg)
            try:
                project.branches.create({'branch': branch_rename,'ref': 'main'}, sudo=user_name)
                project.mergerequests.create({'source_branch':branch_rename,
                                              'target_branch':base_branch,
                                              'title':'Untitled',
                                              'body':'Empty',
                                              'target_project_id':tarject_project_id}, sudo=user_name)
                break
            except gitlab.exceptions.GitlabCreateError:
                attempt +=1
        else:
            msg = {"i":i,
                   "attempt":attempt,
                   "user":user_name,
                   "repo":f"{repo_owner}/{repo_name}",
                   "base":base_branch,
                   "head":branch_rename}
            
            logger.warning('Error creating pull request',extra=msg)
            
def pull_request(gl, i, attempt, user_name, project_name_with_namespace):
    
    user_name  = replace_bot_substring(user_name)
    repo_owner, repo_name = project_name_with_namespace.split('/')
    repo_owner, repo_name = replace_bot_substring(repo_owner),replace_bot_substring(repo_name)
    project_name_with_namespace = replace_bot_substring(project_name_with_namespace)
    head_branch, base_branch = 'head_branch', 'base_branch'
    
    msg = {"i":i,
           "attempt":attempt,
           "user":user_name, 
           "repo":f"{repo_owner}/{repo_name}", 
           "base":base_branch, 
           "head":head_branch}
    
    logger.info('Creating pull request',extra=msg)
    
    # 1. Create user if it does no exist:
    if user_name not in [x.username for x in gl.users.list(search=user_name)]:
        create_user(gl, user_name)

    # 2. Create repo owner user if it does no exist:
    if repo_owner not in [x.username for x in gl.users.list(search=repo_owner)]:
        create_user(gl, repo_owner)

    # 3. Create repo if it does not exist:
    try:
        time.sleep(2)
        project = gl.projects.get(project_name_with_namespace)
    except gitlab.exceptions.GitlabGetError:
        project = create_repo(gl, repo_name, repo_owner, project_name_with_namespace)

    tarject_project_id = project.id

    # 4. Create source (base) branch if it does not exist:
    try:
        time.sleep(1)
        project.branches.get(base_branch)
    except gitlab.exceptions.GitlabGetError:
        project.branches.create({'branch': base_branch,'ref': 'main'}, sudo=repo_owner)

    # 5. Fork project if user_name != repo_owner
    if user_name != repo_owner:
        forked_project = create_fork(gl, project, user_name)

        # 6. Create target (head) branch if it does not exist:
        try:
            time.sleep(1)
            forked_project.branches.get(head_branch)
        except gitlab.exceptions.GitlabGetError:
            forked_project.branches.create({'branch': head_branch,'ref': 'main'}, sudo=user_name)

        # 7. Create merge request (pull request):
        create_pull_request(i, forked_project, head_branch, base_branch, tarject_project_id, user_name,repo_owner, repo_name)

    # if user_name == repo_owner, there is no need to fork
    else:
        # 6. Create target (head) branch if it does not exist:
        try:
            time.sleep(1)
            project.branches.get(head_branch)
        except gitlab.exceptions.GitlabGetError:
            project.branches.create({'branch': head_branch,'ref': 'main'}, sudo=user_name)

        # 7. Create merge request (pull request):
        create_pull_request(i, project, head_branch, base_branch, tarject_project_id, user_name,repo_owner, repo_name)