# from gitlab import Gitlab
import logging
from time import time
import json
import re
import requests
import random
import string
import traceback
from tqdm import tqdm

random.seed(0)

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "\'%(asctime)s\'", "levelname": "%(levelname)s", "message": "%(message)s"},',
    filename="load_dataset_logfile.log",
    filemode="w",
)


class GitlabAPI:
    def __init__(
        self,
        url="http://localhost",
        token="token-string-here1234",
        disable_progress_bar=False,
    ):
        self.headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}
        self.url = url
        self.requests = requests.Session()
        self.username = "root"
        self.progress_bar = disable_progress_bar

    def parse_result(self, result: requests.models.Response):
        if result.text and len(result.text) > 3:
            return json.loads(result.text)
        return {}

    def request_get(self, endpoint: str):
        request = self.requests.get(endpoint, headers=self.headers)
        logging.debug(
            f"Received staus code: {request.status_code}, {request.text}, {endpoint}"
        )
        if request.status_code not in [200, 201, 202, 204]:
            raise ValueError(f"Received staus code: {request.status_code}, {endpoint}")
        return self.parse_result(request)

    def requests_post(self, endpoint: str, data: dict):
        request = self.requests.post(endpoint, headers=self.headers, data=data)
        logging.debug(
            f"Received staus code: {request.status_code}, {request.text}, {endpoint}"
        )
        if request.status_code not in [200, 201, 202, 204]:
            raise ValueError(f"Received staus code: {request.status_code}, {endpoint}")
        return self.parse_result(request)

    def requests_put(self, endpoint, data):
        request = self.requests.put(endpoint, headers=self.headers, data=data)
        logging.debug(
            f"Received staus code: {request.status_code}, {request.text}, {endpoint}"
        )
        if request.status_code not in [200, 201, 202, 204]:
            raise ValueError(f"Received staus code: {request.status_code}, {endpoint}")
        return self.parse_result(request)

    def amend_name(self, name: str):
        # Replace forbidden characters on Gitlab
        validation = re.compile(
            r"^(?!-|\.git$|\.atom$)[a-zA-Z0-9][a-zA-Z0-9_.-]*[a-zA-Z0-9]$"
        )
        try:
            amended_name = re.match(validation, name).string
            return amended_name
        except:
            try:
                amended_name = re.sub(
                    r"\[bot]", "-bot", name, re.IGNORECASE
                )  # replace [bot] for -bot
                amended_name = re.sub(
                    r"^[\W_]+|[\W_]+$", "", amended_name, re.IGNORECASE
                )  # remove leading and trailing special characters
                amended_name = re.match(validation, amended_name).string
                return amended_name
            except:
                amended_name = name.replace(
                    "-", "45"
                )  # for repo named '-', user 'v--' replace hyphen with its ASCII code => 45.
                return amended_name

    def validate(self, source: str, target: str, **kwargs):
        logging.debug("is when this event was logged.")
        self.source_user_data = None
        self.target_user_data = None
        self.target_repo_data = None

        source_user = self.amend_name(source)
        self.source_user_data = self.get_user(source_user)  # get source user
        if not self.source_user_data:
            self.source_user_data = self.create_user(source_user)

        if kwargs["repo"]:
            # if tarject is a repo/project:
            target_user, target_repo = target.split("/")
            target_user, target_repo = self.amend_name(target_user), self.amend_name(
                target_repo
            )
            try:
                self.target_user_data = self.get_user(target_user)
                if not self.target_user_data:
                    logging.debug(f"{target_user} not found, creating user")
                    self.target_user_data = self.create_user(target_user)
            except ValueError:
                logging.debug(f"{target_user} not found, creating user")
                self.target_user_data = self.create_user(target_user)
            try:
                self.target_repo_data = self.get_repo(target_user, target_repo)
            except ValueError:
                logging.debug(f"{target_repo} not found, creating repo")
                self.target_repo_data = self.create_repo(target_repo, target_user)
            finally:
                if isinstance(self.target_repo_data, list):
                    self.target_repo_data = self.target_repo_data[0]

        else:
            # if target is a user:
            target_user = self.amend_name(target)
            self.target_user_data = self.get_user(target_user)  # get target user
            if not self.target_user_data:
                self.target_user_data = self.create_user(target_user)

        if kwargs["invite"]:
            if isinstance(self.source_user_data, list):
                self.source_user_data = self.source_user_data[0]
            if isinstance(self.target_user_data, list):
                self.target_user_data = self.target_user_data[0]
        if kwargs["invite"] and (
            self.source_user_data.get("id") != self.target_user_data.get("id")
        ):
            # if user should be a member od repo/project:
            project_members = self.request_get(
                self.target_repo_data.get("_links").get("members")
            )
            project_members = [member.get("name") for member in project_members]
            if self.source_user_data.get("name") not in project_members:
                self.create_invitation(
                    self.target_repo_data.get("id"),
                    self.source_user_data.get("id"),
                    self.target_user_data.get("id"),
                )

    def get_user(self, user_name: str):
        endpoint = f"{self.url}/api/v4/users?username={user_name}"
        return self.request_get(endpoint)

    def get_repo(self, repo_owner: str, repo_name: str):
        endpoint = f"{self.url}/api/v4/projects/{repo_owner}%2F{repo_name}"
        return self.request_get(endpoint)

    def create_user(self, user_name: str):
        endpoint = f"{self.url}/api/v4/users"
        user_data = json.dumps(
            {
                "email": user_name + "@mail.com",
                "username": user_name,
                "name": user_name,
                "reset_password": False,
                "password": "soci@lz-psw-2023",
                "skip_confirmation": True,
            }
        )
        return self.requests_post(endpoint, data=user_data)

    def create_repo(self, repo_name: str, user: str):
        # creates a new project owned by the specified user
        endpoint = f"{self.url}/api/v4/projects?sudo={user}"  #  -> sudo could be either name or id #.
        project_data = json.dumps(
            {"name": repo_name, "visibility": "public", "initialize_with_readme": True}
        )
        return self.requests_post(endpoint, data=project_data)

    def create_invitation(self, project_id: int, user_id: str, user: int):
        # create invitation for {user_id} to colaborate on {project_id}, impersonate repo owner sudo={user}
        endpoint = f"{self.url}/api/v4/projects/{project_id}/members?sudo={user}"
        invitation_data = json.dumps({"user_id": user_id, "access_level": 50})

        return self.requests_post(endpoint, data=invitation_data)

    def watch(self, project_id: int, user: str):
        # Star a project (repo)
        endpoint = f"{self.url}/api/v4/projects/{project_id}/star?sudo={user}"
        return self.requests_post(endpoint, data={})

    def unwatch(self, project_id: int, user: str):
        # Unstar a project (repo)
        endpoint = f"{self.url}/api/v4/projects/{project_id}/unstar?sudo={user}"
        return self.requests_post(endpoint, data={})

    def follow(self, user_id, user):
        # Create a follow relation between one user {user} to another {user_id}. -> user_id follows user
        endpoint = f"{self.url}/api/v4/users/{str(user_id)}/follow?sudo={user}"
        return self.requests_post(endpoint, data={})

    def unfollow(self, user_id, user):
        # user_id unfollows user
        endpoint = f"{self.url}/api/v4/users/{user_id}/unfollow?sudo={user}"
        return self.requests_post(endpoint, data={})

    def fork(self, project_id, user, data):
        # user forks project_id
        endpoint = f"{self.url}/api/v4/projects/{project_id}/fork?sudo={user}"
        return self.requests_post(endpoint, data=data)

    def get_branches(self, project_id):
        # NOTE: if Returns an empty list, means only project.get('default_branch') exists.
        endpoint = f"{self.url}/api/v4/projects/{project_id}/repository/branches"
        return self.request_get(endpoint)

    def commit(self, project_id, branch, user, action="update"):
        # POST /projects/:id/repository/commits
        endpoint = (
            f"{self.url}/api/v4/projects/{project_id}/repository/commits?sudo={user}"
        )
        commit_data = json.dumps(
            {
                "branch": branch,
                "commit_message": f'{self.random_text_generator("title")}\n{self.random_text_generator("message")}',
                "actions": [
                    {
                        "action": action,
                        "file_path": "README.md",
                        "content": self.random_text_generator("body"),
                    }
                ],
            }
        )
        return self.requests_post(endpoint, data=commit_data)

    def create_branch(self, branch_name, project_id, user):
        endpoint = (
            f"{self.url}/api/v4/projects/{project_id}/repository/branches?sudo={user}"
        )
        branch_data = json.dumps({"branch": branch_name, "ref": "main"})
        return self.requests_post(endpoint, data=branch_data)

    def pull_request(self, project_id, head_branch, base_branch="main"):
        # POST /projects/:id/merge_requests
        endpoint = f"{self.url}/api/v4/projects/{project_id}/merge_requests"
        request_data = json.dumps(
            {
                "source_branch": head_branch,
                "target_branch": base_branch,
                "title": self.random_text_generator("title"),
                "body": self.random_text_generator("body"),
                "target_project_id": project_id,
            }
        )

        return self.requests_post(endpoint, data=request_data)

    def merge_pull_request(self, project_id, merge_request_iid, user):
        # PUT /projects/:id/merge_requests/:merge_request_iid/merge
        endpoint = f"{self.url}/projects/{project_id}/merge_requests/{merge_request_iid}/merge?sudo={user}"
        merge_data = json.dumps(
            {
                "merge_commit_message": self.random_text_generator("message"),
                "should_remove_source_branch": True,
            }
        )
        return self.requests_put(endpoint, data=merge_data)

    def update_pull_request(self, project_id, merge_request_iid, state_event, user):
        endpoint = f"{self.url}/api/v4/projects/{project_id}/merge_requests/{merge_request_iid}?sudo={user}"
        request_data = json.dumps({"state_event": state_event})
        return self.requests_put(endpoint, data=request_data)

    def get_pull_requests(self, project_id):
        endpoint = f"{self.url}/api/v4/projects/{project_id}/merge_requests"
        return self.request_get(endpoint)

    # def wait(self, function, wait_time=0.25, max_attempts=5):
    #     # exponential backoff strategy, doubling on retries to prevent system overload during checks.
    #     attempt = 0
    #     while attempt < max_attempts:
    #         try:
    #             result = function
    #             return result
    #         except Exception as e:
    #             attempt += 1
    #             time.sleep(wait_time*attempt)
    #             continue
    #     # Return None if max_attempts reached without success
    #     return None

    def create_pull_request(self, source: str, target: str):
        self.validate(source, target, repo=True, invite=True)
        repo_data = self.target_repo_data

        head_branch, base_branch = "head", "main"
        branches = self.get_branches(project_id=repo_data.get("id"))

        if not branches:
            # if only 'main' branch exist, create 'head' branch.
            self.create_branch(
                branch_name=head_branch,
                project_id=repo_data.get("id"),
                user=self.source_user_data.get("id"),
            )
            self.pull_request(
                project_id=repo_data.get("id"),
                head_branch=head_branch,
                base_branch=base_branch,
            )
        else:
            pull_requests = self.get_pull_requests(project_id=repo_data.get("id"))
            if len(pull_requests) >= 1:
                pr = random.choice(pull_requests)
                status = pr.get("state")
                try:
                    self.merge_pull_request(
                        project_id=repo_data.get("id"),
                        merge_request_iid=pr.get("iid"),
                        user=self.source_user_data.get("id"),
                    )
                except:
                    logging.debug("couldn't be merged...")
                    if status == "closed":
                        self.update_pull_request(
                            repo_data.get("id"),
                            pr.get("iid"),
                            state_event="reopen",
                            user=self.source_user_data.get("id"),
                        )
                    if status == "opened":
                        self.update_pull_request(
                            repo_data.get("id"),
                            pr.get("iid"),
                            state_event="close",
                            user=self.source_user_data.get("id"),
                        )
                    if status == "merged":
                        # create new branch and merge it
                        self.create_branch(
                            branch_name=head_branch,
                            project_id=repo_data.get("id"),
                            user=self.source_user_data.get("id"),
                        )
                        self.pull_request(
                            project_id=repo_data.get("id"),
                            head_branch=head_branch,
                            base_branch=base_branch,
                        )

    def create_commit(self, source: str, target: str):
        self.validate(source, target, repo=True, invite=True)
        repo_data = self.target_repo_data
        user = self.source_user_data.get("id")
        branches = [
            branch.get("name")
            for branch in self.get_branches(project_id=repo_data.get("id"))
        ]
        if branches:
            logging.debug(f"branches: {branches}")
            branch = random.choice(branches)
        else:
            logging.debug(f'only defaul branch {repo_data.get("default_branch")}')
            branch = repo_data.get("default_branch")  # NOTE: should be 'main'

        self.commit(
            project_id=repo_data.get("id"), branch=branch, user=user
        )  # TODO: try/except if error: commit into another branch

    def create_fork(self, source: str, target: str, max_atttemps=5):
        self.validate(source, target, repo=True, invite=False)
        project_id = self.target_repo_data.get("id")
        try:
            self.fork(project_id, source, {})
        except ValueError:
            logging.debug("project already forked, trying different name")
            attempt = 0
            project_name = self.target_repo_data.get("name")
            while attempt < max_atttemps:
                try:
                    self.fork(
                        project_id,
                        source,
                        json.dumps(
                            {
                                "name": project_name
                                + "_"
                                + source
                                + "_"
                                + str(attempt),
                                "path": source + "_" + str(attempt),
                            }
                        ),
                    )
                except:
                    logging.debug("trying different name...")
                    attempt += 1
                    continue
                break

    def create_watch(self, source: str, target: str):
        self.validate(source, target, repo=True, invite=False)
        project_id = self.target_repo_data.get("id")
        try:
            self.watch(project_id, source)
        except ValueError:
            self.unwatch(project_id, source)

    def create_follow(self, source: str, target: str):
        self.validate(source, target, repo=False, invite=False)
        user_id = self.get_user(source)[0].get("id")
        try:
            self.follow(user_id, target)
        except ValueError:
            self.unfollow(user_id, target)

    def random_text_generator(self, text_type):
        text_lengths = {"title": (18, 42), "body": (42, 437), "message": (19, 100)}
        min_length, max_length = text_lengths.get(text_type, (0, 0))

        n = random.randint(min_length, max_length)
        text = " ".join(
            [
                "".join(random.choices(string.ascii_lowercase, k=random.randint(2, 8)))
                for _ in range(n)
            ]
        )

        return text

    def clean_message(self, text):
        clean = re.sub(r"\s+", " ", text)
        clean = re.sub(r"[\"']", "", clean)
        return clean

    def flow(self, edge_list):
        logging.info(f"Workflow started")
        for i in (pbar := tqdm(edge_list.index, disable=self.progress_bar)):
            source, target = edge_list.loc[i, "source"].lstrip("ur: "), edge_list.loc[
                i, "target"
            ].lstrip("ur: ")
            attempt = 0
            while attempt < 5:
                attempt += 1
                try:
                    if edge_list.loc[i, "type"] == "PullRequestEvent":
                        self.create_pull_request(source, target)
                        pbar.set_description(f"{i} PullRequestEvent created")
                        logging.info(f"{i} PullRequestEvent created")
                    if edge_list.loc[i, "type"] == "PushEvent":
                        self.create_commit(source, target)
                        pbar.set_description(f"{i} PushEvent created")
                        logging.info(f"{i} PushEvent created")
                    if edge_list.loc[i, "type"] == "ForkEvent":
                        self.create_fork(source, target)
                        pbar.set_description(f"{i} ForkEvent created")
                        logging.info(f"{i} ForkEvent created")
                    if edge_list.loc[i, "type"] == "WatchEvent":
                        self.create_watch(source, target)
                        pbar.set_description(f"{i} WatchEvent created")
                        logging.info(f"{i} WatchEvent created")
                    if edge_list.loc[i, "type"] == "FollowEvent":
                        self.create_follow(source, target)
                        pbar.set_description(f"{i} FollowEvent created")
                        logging.info(f"{i} FollowEvent created")
                    elif edge_list.loc[i, "type"] not in [
                        "PullRequestEvent",
                        "PushEvent",
                        "ForkEvent",
                        "WatchEvent",
                        "FollowEvent",
                    ]:
                        logging.critical(
                            f"{i} {edge_list.loc[i, 'type']} Event not allowed"
                        )
                        break
                except Exception as e:
                    error = str(e)
                    tb = traceback.format_exc()
                    pbar.set_description(f"Error on: {i} attempt: {attempt}")
                    logging.warning(
                        f"{i} {self.clean_message(str(edge_list.loc[i,:]))} Error message: {self.clean_message(error)}"
                    )
                    continue
                break
            else:
                logging.critical(
                    f'{i} {edge_list.loc[i, "type"]} Error messages: {self.clean_message(error)} {self.clean_message(tb)}'
                )
        logging.info(f"Workflow endend")
