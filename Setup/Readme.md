# Install Gitlab - Docker:

Run:
```
docker run \
  --detach \
  --restart always \
  --name gitlab-ce \
  --privileged \
  --memory 4096M \
  --publish 22:22 \
  --publish 80:80 \
  --publish 443:443 \
  --publish 9090:9090 \
  --env GITLAB_OMNIBUS_CONFIG=" \
    external_url 'http://localhost';
    node_exporter['enable'] = true;
    grafana['enable'] = true;
    nginx['redirect_http_to_https'] = true; "\
  --volume /srv/gitlab-ce/conf:/etc/gitlab:z \
  --volume /srv/gitlab-ce/logs:/var/log/gitlab:z \
  --volume /srv/gitlab-ce/data:/var/opt/gitlab:z \
  yrzr/gitlab-ce-arm64v8:latest
```
Set root password:
```docker exec -it gitlab-ce gitlab-rake 'gitlab:password:reset[root]'```

Some helper functions in case of need to change configurations:   

3.1 Docker:
```
docker kill gitlab-ce # terminates the container.
docker rm gitlab-ce # removes the container.
sudo rm -r /srv/gitlab-ce/ # removes data.
docker ps # shows running containers.
```
3.2 Gitlab:
```
sudo docker logs -f gitlab # check logs.
docker exec -it gitlab-ce editor /etc/gitlab/gitlab.rb # edit configurations.
docker exec -it gitlab-ce gitlab-ctl reconfigure # reconfigure changes.
```
3.3 Vim (To edit configurations):
```
i Start insert mode at/after cursor.
Esc Exit insert mode.
dd Delete line.
:wq Write (save) and quit.
:q! Quit and throw away changes.
/pattern Search for pattern.
n Repeat search in same direction.
```
