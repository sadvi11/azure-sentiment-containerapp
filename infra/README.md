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

## Production upgrade

This demo uses ACR **admin credentials** for simplicity. In production, give the
Container App a **managed identity** and grant it `AcrPull` on the registry
instead of using a username/password secret.
