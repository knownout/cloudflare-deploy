# Cloudflare DNS deployment script
Simple python script for DNS deployment, designed to run within gitlab CI/CD
pipeline and automatically handle cases when new website or subdomain is
deployed


### Script arguments list

| Argument     | Required | Default | Description                                                     |
|--------------|----------|---------|-----------------------------------------------------------------|
| --zone       | Yes      |         | Set zone alias defined in api-access.json file                  |
| --name       | Yes      |         | Set new record name (sub-domain for zone alias)                 |
| --ttl        |          | 1       | Set new record time to live (from 3600 to 86400, 1 - automatic) |
| --type       |          | A       | Set new DNS record type (A, AAAA, CNAME, ...)                   |
| --proxied    |          | True    | Set proxy enabled or disabled for new record                    |
| --erase      |          | False   | Erase specified proxy instead of creating it                    |
| --silent     |          | False   | Run script without any output except errors                     |
| --help       |          |         | Show script help menu                                           |
| --regenerate |          |         | Create new stub configuration file if not exist                 |

<br>

re-knownout - [https://github.com/re-knownout/](https://github.com/re-knownout/)
<br> [knownout@hotmail.com](mailto:knownout@hotmail.com)