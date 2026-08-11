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
az acr create -g $RG -n $ACR --sku Basic --admin-enabled true

# build the image in the cloud (no local Docker needed)
az acr build --registry $ACR --image sentiment-api:v1 .

# If that fails with TasksOperationsNotAllowed, ACR Tasks is not enabled on
# your subscription (common on free/trial). Build and push locally instead --
# --platform linux/amd64 matters on Apple Silicon, since Container Apps is x86:
#   az acr login --name $ACR
#   docker build --platform linux/amd64 -t $ACR.azurecr.io/sentiment-api:v1 .
#   docker push $ACR.azurecr.io/sentiment-api:v1

# deploy infra + app
ACR_SERVER=$(az acr show -n $ACR --query loginServer -o tsv)
ACR_USER=$(az acr credential show -n $ACR --query username -o tsv)
ACR_PASS=$(az acr credential show -n $ACR --query 'passwords[0].value' -o tsv)

az deployment group create -g $RG --template-file infra/main.bicep \
  --parameters appName=sentiment-api \
    containerImage="$ACR_SERVER/sentiment-api:v1" \
    acrLoginServer="$ACR_SERVER" acrUsername="$ACR_USER" acrPassword="$ACR_PASS"
```

## Cost

Azure Container Apps bills per-second only while running and **scales to zero**
(`minReplicas: 0`), so an idle demo costs ~nothing. ACR Basic is ~$5/month —
delete the resource group when you are done:

```bash
az group delete -n sentiment-rg --yes --no-wait
```

## Production upgrade: drop the ACR admin account

This demo uses ACR **admin credentials** for simplicity, and that is the weakest
link in the setup. The admin account is a single shared username/password with
full push *and* pull rights, it cannot be scoped down, and it is stored as a
secret on the Container App. Azure recommends leaving it disabled.

The fix is a **managed identity** with a scoped `AcrPull` role, so no password
exists anywhere:

```bash
RG=sentiment-rg; APP=sentiment-api; ACR=your-unique-acr-name

# 1. Give the container app a system-assigned identity
az containerapp identity assign -g $RG -n $APP --system-assigned

# 2. Grant that identity pull-only access to the registry
PRINCIPAL=$(az containerapp show -g $RG -n $APP --query identity.principalId -o tsv)
ACR_ID=$(az acr show -n $ACR --query id -o tsv)
az role assignment create --assignee "$PRINCIPAL" --role AcrPull --scope "$ACR_ID"

# 3. Point the app at the registry via that identity, then turn admin off
az containerapp registry set -g $RG -n $APP --server "$ACR.azurecr.io" --identity system
az acr update -n $ACR --admin-enabled false
```

Ordering matters: the identity must exist and hold `AcrPull` *before* the app
tries its next image pull, which is why this runs after the first deploy rather
than inside `main.bicep`.

> **Handling the admin password until then:** it is fetched at deploy time
> rather than stored in the repo, the Bicep parameter is marked `@secure()` so
> it stays out of Azure deployment history, and CI masks it with `::add-mask::`
> so it cannot surface in public build logs. Never paste it into a terminal
> where it would land in shell history — always capture it via `$(...)` as above.
