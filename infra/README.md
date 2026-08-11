# Infrastructure (Bicep)

`main.bicep` provisions everything the app needs on Azure:

| Resource | Purpose |
|----------|---------|
| Log Analytics workspace | Central logs for the environment |
| Container Apps managed environment | The serverless runtime that hosts the app |
| Container App | Runs the container, external HTTPS ingress, autoscaling 0→5 |

## Deploy manually (the pipeline does this for you)

```bash
RG=sentiment-rg
LOCATION=canadacentral
ACR=your-unique-acr-name        # must be globally unique, lowercase

az group create -n $RG -l $LOCATION
az acr create -g $RG -n $ACR --sku Basic --admin-enabled false

# build the image in the cloud (no local Docker needed)
az acr build --registry $ACR --image sentiment-api:v1 .

# If that fails with TasksOperationsNotAllowed, ACR Tasks is not enabled on
# your subscription (common on free/trial). Build and push locally instead --
# --platform linux/amd64 matters on Apple Silicon, since Container Apps is x86:
#   az acr login --name $ACR
#   docker build --platform linux/amd64 -t $ACR.azurecr.io/sentiment-api:v1 .
#   docker push $ACR.azurecr.io/sentiment-api:v1

# deploy infra + app -- no registry credentials anywhere
ACR_SERVER=$(az acr show -n $ACR --query loginServer -o tsv)

az deployment group create -g $RG --template-file infra/main.bicep \
  --parameters appName=sentiment-api \
    containerImage="$ACR_SERVER/sentiment-api:v1" \
    acrLoginServer="$ACR_SERVER"

# One-time bootstrap: the app gets a system-assigned identity from the
# template, but the role granting it pull rights has to be created once, after
# the identity exists. Until then the app cannot pull.
PRINCIPAL=$(az containerapp show -g $RG -n sentiment-api --query identity.principalId -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL" \
  --assignee-principal-type ServicePrincipal \
  --role AcrPull --scope "$(az acr show -n $ACR --query id -o tsv)"
```

> **Chicken-and-egg, and why it is a separate step:** the role assignment needs
> the identity's principal ID, which does not exist until the app is created.
> Bicep cannot express that in one pass for a system-assigned identity, so this
> runs once per environment. Redeploys reuse the same principal, so the role
> keeps applying and the step never repeats.
>
> Note this requires permission to create role assignments (Owner or User Access
> Administrator). A plain Contributor service principal **cannot** do it, which
> is why this is a human bootstrap step rather than something CI performs.

## Cost

Azure Container Apps bills per-second only while running and **scales to zero**
(`minReplicas: 0`), so an idle demo costs ~nothing. ACR Basic is ~$5/month —
delete the resource group when you are done:

```bash
az group delete -n sentiment-rg --yes --no-wait
```

## Registry authentication: no passwords anywhere

The ACR **admin account is disabled**. It is a single shared username/password
carrying both push *and* pull rights, it cannot be scoped down, and using it
means storing that password as a secret on the Container App. Azure recommends
leaving it off, and this deployment does.

Instead, each side authenticates as itself:

| Who | How it authenticates | Rights |
|-----|----------------------|--------|
| Container App (pull) | System-assigned managed identity | `AcrPull` on this one registry |
| CI / you (push) | Your own Azure login (`az acr login`) | Whatever your own role grants |

Consequences worth knowing:

- `az acr credential show` **fails by design**. Nothing should be asking for a
  registry password — if some command needs one, that command is the problem.
- The Container App has **zero secrets**. There is no registry password to
  leak, rotate, or accidentally print into a log.
- The identity's `AcrPull` is scoped to this registry alone, and is pull-only —
  a compromised app cannot push a poisoned image back.

To confirm the posture at any time:

```bash
az acr show -n $ACR --query adminUserEnabled                  # false
az containerapp secret list -g $RG -n sentiment-api           # []
az containerapp show -g $RG -n sentiment-api --query identity.type   # SystemAssigned
```
